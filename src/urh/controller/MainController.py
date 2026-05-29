import copy
import os

from PyQt6.QtCore import QDir, Qt, pyqtSlot, QTimer, QSize
from PyQt6.QtGui import (
    QIcon,
    QCloseEvent,
    QKeySequence,
    QUndoGroup,
    QActionGroup,
    QAction,
)
from PyQt6.QtWidgets import (
    QMainWindow,
    QHeaderView,
    QMessageBox,
    QApplication,
    QVBoxLayout,
    QListWidgetItem,
    QFileDialog,
    QWidget,
    QLabel,
    QFrame,
)

from urh import settings, version
from urh.controller.CompareFrameController import CompareFrameController
from urh.controller.SignalTabController import SignalTabController
from urh.controller.dialogs.OptionsDialog import OptionsDialog
from urh.controller.dialogs.ProjectDialog import ProjectDialog
from urh.controller.dialogs.ProtocolSniffDialog import ProtocolSniffDialog
from urh.controller.dialogs.ReceiveDialog import ReceiveDialog
from urh.controller.dialogs.GaussianNoiseDialog import GaussianNoiseDialog
from urh.controller.dialogs.SendDialog import SendDialog
from urh.controller.dialogs.SpectrumDialogController import SpectrumDialogController
from urh.controller.widgets.SignalFrame import SignalFrame
from urh.models.FileFilterProxyModel import FileFilterProxyModel
from urh.models.FileIconProvider import FileIconProvider
from urh.models.FileSystemModel import FileSystemModel
from urh.models.ParticipantLegendListModel import ParticipantLegendListModel
from urh.plugins.PluginManager import PluginManager
from urh.signalprocessing.ProtocolAnalyzer import ProtocolAnalyzer
from urh.signalprocessing.Signal import Signal
from urh.ui import icon_theme
from urh.ui.ui_main import Ui_MainWindow
from urh.util import FileOperator, util
from urh.util.Errors import Errors
from urh.util.Logger import logger
from urh.util.ProjectManager import ProjectManager


class MainController(QMainWindow):
    SIGNAL_FILE_SUFFIXES = (
        ".complex",
        ".coco",
        ".wav",
        ".wave",
        ".complex16s",
        ".complex16u",
        ".complex32s",
        ".complex32u",
        ".cs8",
        ".cu8",
        ".cs16",
        ".cu16",
    )
    DEFAULT_PROTO_VIEW_INDEX = 1

    def __init__(self, *args):
        super().__init__(*args)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._create_noise_tab()

        util.set_splitter_stylesheet(self.ui.splitter)

        OptionsDialog.write_default_options()

        self.project_save_timer = QTimer()
        self.project_manager = ProjectManager(self)
        self.plugin_manager = PluginManager()
        self.signal_source_directory = None
        self.signal_tab_controller = SignalTabController(
            self.project_manager, parent=self.ui.tab_interpretation
        )
        self.ui.tab_interpretation.layout().addWidget(self.signal_tab_controller)
        self.compare_frame_controller = CompareFrameController(
            parent=self.ui.tab_protocol,
            plugin_manager=self.plugin_manager,
            project_manager=self.project_manager,
        )
        self.compare_frame_controller.ui.splitter.setSizes([1, 1000000])

        self.ui.tab_protocol.layout().addWidget(self.compare_frame_controller)
        self.embedded_spectrum_controller = None
        self.embedded_repeat_dialog = None
        self.embedded_noise_dialog = None

        self.__enable_replay_only_mode()

        self.undo_group = QUndoGroup()
        self.undo_group.addStack(self.signal_tab_controller.signal_undo_stack)
        self.undo_group.addStack(self.compare_frame_controller.protocol_undo_stack)
        self.undo_group.setActiveStack(self.signal_tab_controller.signal_undo_stack)

        self.cancel_action = QAction(self.tr("Cancel"), self)
        self.cancel_action.setShortcut(
            QKeySequence.StandardKey.Cancel
            if hasattr(QKeySequence, "Cancel")
            else "Esc"
        )
        self.cancel_action.triggered.connect(self.on_cancel_triggered)
        self.cancel_action.setShortcutContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.cancel_action.setIcon(QIcon.fromTheme("dialog-cancel"))
        self.addAction(self.cancel_action)

        self.ui.actionAuto_detect_new_signals.setChecked(
            settings.read("auto_detect_new_signals", True, bool)
        )

        self.participant_legend_model = ParticipantLegendListModel(
            self.project_manager.participants
        )
        self.ui.listViewParticipants.setModel(self.participant_legend_model)

        self.signal_protocol_dict = {}  # type: dict[SignalFrame, ProtocolAnalyzer]

        self.ui.lnEdtTreeFilter.setClearButtonEnabled(True)

        group = QActionGroup(self)
        self.ui.actionFSK.setActionGroup(group)
        self.ui.actionOOK.setActionGroup(group)
        self.ui.actionNone.setActionGroup(group)
        self.ui.actionPSK.setActionGroup(group)

        noise_threshold_setting = settings.read("default_noise_threshold", "automatic")
        noise_threshold_group = QActionGroup(self)
        self.ui.actionAutomaticNoiseThreshold.setActionGroup(noise_threshold_group)
        self.ui.actionAutomaticNoiseThreshold.setChecked(
            noise_threshold_setting == "automatic"
        )
        self.ui.action1NoiseThreshold.setActionGroup(noise_threshold_group)
        self.ui.action1NoiseThreshold.setChecked(noise_threshold_setting == "1")
        self.ui.action5NoiseThreshold.setActionGroup(noise_threshold_group)
        self.ui.action5NoiseThreshold.setChecked(noise_threshold_setting == "5")
        self.ui.action10NoiseThreshold.setActionGroup(noise_threshold_group)
        self.ui.action10NoiseThreshold.setChecked(noise_threshold_setting == "10")
        self.ui.action100NoiseThreshold.setActionGroup(noise_threshold_group)
        self.ui.action100NoiseThreshold.setChecked(noise_threshold_setting == "100")

        self.recentFileActionList = []
        self.create_connects()
        self.__setup_embedded_panels()
        self.__localize_replay_only_ui()
        self.update_signal_source_labels()
        self.init_recent_file_action_list(settings.read("recentFiles", [], list))

        self.filemodel = FileSystemModel(self)
        path = QDir.homePath()

        self.filemodel.setIconProvider(FileIconProvider())
        self.filemodel.setRootPath(path)
        self.file_proxy_model = FileFilterProxyModel(self)
        self.file_proxy_model.setSourceModel(self.filemodel)
        self.ui.fileTree.setModel(self.file_proxy_model)

        self.ui.fileTree.setRootIndex(
            self.file_proxy_model.mapFromSource(self.filemodel.index(path))
        )
        self.ui.fileTree.setToolTip(path)
        self.ui.fileTree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.ui.fileTree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.ui.fileTree.setFocus()

        self.initialize_default_signal_directory(load_files=True)

        self.ui.actionConvert_Folder_to_Project.setEnabled(False)

        undo_action = self.undo_group.createUndoAction(self)
        undo_action.setIcon(QIcon.fromTheme("edit-undo"))
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.ui.menuEdit.insertAction(self.ui.actionOptions, undo_action)

        redo_action = self.undo_group.createRedoAction(self)
        redo_action.setIcon(QIcon.fromTheme("edit-redo"))
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.ui.menuEdit.insertAction(self.ui.actionOptions, redo_action)
        self.ui.menuEdit.insertSeparator(self.ui.actionOptions)
        self.ui.actionAbout_Qt.setIcon(
            QIcon(":/qt-project.org/qmessagebox/images/qtlogo-64.png")
        )

        self.__set_non_project_warning_visibility()

        self.ui.splitter.setSizes([0, 1])
        self.refresh_main_menu()

        self.apply_default_view(settings.read("default_view", type=int))
        self.project_save_timer.start(
            ProjectManager.AUTOSAVE_INTERVAL_MINUTES * 60 * 1000
        )

        self.ui.actionProject_settings.setVisible(False)
        self.ui.actionSave_project.setVisible(False)
        self.ui.actionClose_project.setVisible(False)

        self.restoreGeometry(
            settings.read("{}/geometry".format(self.__class__.__name__), type=bytes)
        )
        self.__apply_primary_button_icons()

    def __enable_replay_only_mode(self):
        for tab in (self.ui.tab_protocol,):
            index = self.ui.tabWidget.indexOf(tab)
            if index >= 0:
                self.ui.tabWidget.removeTab(index)

        ordered_tabs = (
            (self.ui.tab_waterfall, self.tr("Водопад")),
            (self.ui.tab_interpretation, self.tr("Сигналы")),
            (self.ui.tab_repeat, self.tr("Повтор")),
            (self.tab_noise, self.tr("Гауссовский шум")),
        )
        for tab, _label in ordered_tabs:
            index = self.ui.tabWidget.indexOf(tab)
            if index >= 0:
                self.ui.tabWidget.removeTab(index)
        for index, (tab, label) in enumerate(ordered_tabs):
            self.ui.tabWidget.insertTab(index, tab, label)
        self.ui.tabWidget.setCurrentWidget(self.ui.tab_waterfall)

        self.compare_frame_controller.hide()
        self.ui.menuImport.menuAction().setVisible(False)
        self.ui.actionSpectrum_Analyzer.setVisible(False)
        self.ui.actionSniff_protocol.setVisible(False)
        self.ui.actionConvert_Folder_to_Project.setVisible(False)
        self.ui.actionAuto_detect_new_signals.setVisible(False)

    def __apply_primary_button_icons(self):
        icon_size = QSize(18, 18)
        self.ui.btnRecordFromWaterfall.setIcon(icon_theme.get_icon("media-record"))
        self.ui.btnRecordFromWaterfall.setIconSize(icon_size)
        self.ui.btnChooseReplayFolder.setIcon(icon_theme.get_icon("folder-open"))
        self.ui.btnChooseReplayFolder.setIconSize(icon_size)
        self.ui.btnOpenSignalForReplay.setIcon(icon_theme.get_icon("document-open"))
        self.ui.btnOpenSignalForReplay.setIconSize(icon_size)

    def _create_noise_tab(self):
        self.tab_noise = QWidget()
        self.tab_noise.setObjectName("tab_noise")

        layout = QVBoxLayout(self.tab_noise)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        self.labelNoiseTabTitle = QLabel("Гауссовский шум", self.tab_noise)
        self.labelNoiseTabTitle.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(self.labelNoiseTabTitle)

        self.labelNoiseTabHint = QLabel(
            "Отдельная вкладка для передачи непрерывного AWGN на выбранной частоте. "
            "Используй ее для тестов приемника и визуальной калибровки водопада.",
            self.tab_noise,
        )
        self.labelNoiseTabHint.setWordWrap(True)
        self.labelNoiseTabHint.setStyleSheet(
            "font-size: 13px; color: rgba(226, 232, 240, 0.78);"
        )
        layout.addWidget(self.labelNoiseTabHint)

        self.frameNoiseHost = QFrame(self.tab_noise)
        self.frameNoiseHost.setFrameShape(QFrame.Shape.StyledPanel)
        self.frameNoiseHost.setStyleSheet(
            "QFrame#frameNoiseHost {"
            "border: 1px solid rgba(96, 165, 250, 0.22);"
            "border-radius: 14px;"
            "}"
        )
        self.frameNoiseHost.setObjectName("frameNoiseHost")
        host_layout = QVBoxLayout(self.frameNoiseHost)
        host_layout.setContentsMargins(0, 0, 0, 0)

        self.noiseContainer = QWidget(self.frameNoiseHost)
        self.noiseContainer.setObjectName("noiseContainer")
        host_layout.addWidget(self.noiseContainer)
        layout.addWidget(self.frameNoiseHost)

        self.ui.tabWidget.addTab(self.tab_noise, self.tr("Гауссовский шум"))

    def __set_non_project_warning_visibility(self):
        show = (
            settings.read("show_non_project_warning", True, bool)
            and not self.project_manager.project_loaded
        )
        self.ui.labelNonProjectMode.setVisible(show)

    def create_connects(self):
        self.ui.actionFullscreen_mode.setShortcut(QKeySequence.StandardKey.FullScreen)
        self.ui.actionOpen.setShortcut(QKeySequence(QKeySequence.StandardKey.Open))
        self.ui.actionOpen_directory.setShortcut(QKeySequence("Ctrl+Shift+O"))

        self.ui.menuEdit.aboutToShow.connect(self.on_edit_menu_about_to_show)

        self.ui.actionNew_Project.triggered.connect(
            self.on_new_project_action_triggered
        )
        self.ui.actionNew_Project.setShortcut(QKeySequence.StandardKey.New)
        self.ui.actionProject_settings.triggered.connect(
            self.on_project_settings_action_triggered
        )
        self.ui.actionSave_project.triggered.connect(self.save_project)
        self.ui.actionClose_project.triggered.connect(self.close_project)
        self.ui.actionExit_App.triggered.connect(self.close)

        self.ui.actionAbout_AutomaticHacker.triggered.connect(
            self.on_show_about_clicked
        )
        self.ui.actionRecord.triggered.connect(
            self.on_show_record_dialog_action_triggered
        )
        self.ui.btnRecordFromWaterfall.clicked.connect(
            self.on_show_record_dialog_action_triggered
        )
        self.ui.btnOpenSignalForReplay.clicked.connect(
            self.on_open_signal_files_requested
        )
        self.ui.btnChooseReplayFolder.clicked.connect(
            self.on_choose_signal_folder_requested
        )

        self.ui.actionFullscreen_mode.triggered.connect(
            self.on_fullscreen_action_triggered
        )
        self.ui.actionSaveAllSignals.triggered.connect(
            self.signal_tab_controller.save_all
        )
        self.ui.actionCloseAllFiles.triggered.connect(
            self.on_close_all_files_action_triggered
        )
        self.ui.actionOpen.triggered.connect(self.on_open_signal_files_requested)
        self.ui.actionOpen_directory.triggered.connect(
            self.on_open_directory_action_triggered
        )
        self.ui.actionSpectrum_Analyzer.triggered.connect(
            self.on_show_spectrum_dialog_action_triggered
        )
        self.ui.actionOptions.triggered.connect(
            self.show_options_dialog_action_triggered
        )
        self.ui.actionSniff_protocol.triggered.connect(self.show_proto_sniff_dialog)
        self.ui.actionAbout_Qt.triggered.connect(QApplication.aboutQt)
        self.ui.actionSamples_from_csv.triggered.connect(
            self.on_import_samples_from_csv_action_triggered
        )
        self.ui.actionAuto_detect_new_signals.triggered.connect(
            self.on_auto_detect_new_signals_action_triggered
        )

        self.ui.actionAutomaticNoiseThreshold.triggered.connect(
            self.on_action_automatic_noise_threshold_triggered
        )
        self.ui.action1NoiseThreshold.triggered.connect(
            self.on_action_1_noise_threshold_triggered
        )
        self.ui.action5NoiseThreshold.triggered.connect(
            self.on_action_5_noise_threshold_triggered
        )
        self.ui.action10NoiseThreshold.triggered.connect(
            self.on_action_10_noise_threshold_triggered
        )
        self.ui.action100NoiseThreshold.triggered.connect(
            self.on_action_100_noise_threshold_triggered
        )

        self.ui.btnFileTreeGoUp.clicked.connect(self.on_btn_file_tree_go_up_clicked)
        self.ui.fileTree.directory_open_wanted.connect(
            self.project_manager.set_project_folder
        )

        self.signal_tab_controller.frame_closed.connect(self.close_signal_frame)
        self.signal_tab_controller.signal_created.connect(self.on_signal_created)
        self.signal_tab_controller.ui.scrollArea.files_dropped.connect(
            self.on_files_dropped
        )
        self.signal_tab_controller.files_dropped.connect(self.on_files_dropped)
        self.signal_tab_controller.frame_was_dropped.connect(self.set_frame_numbers)
        self.signal_tab_controller.record_signal_requested.connect(
            self.on_show_record_dialog_action_triggered
        )
        self.signal_tab_controller.open_signal_requested.connect(
            self.on_open_signal_files_requested
        )
        self.signal_tab_controller.choose_folder_requested.connect(
            self.on_choose_signal_folder_requested
        )
        self.ui.listWidgetReplaySignals.currentRowChanged.connect(
            self.on_replay_signal_list_current_row_changed
        )

        self.compare_frame_controller.show_interpretation_clicked.connect(
            self.show_protocol_selection_in_interpretation
        )
        self.compare_frame_controller.files_dropped.connect(self.on_files_dropped)
        self.compare_frame_controller.ui.treeViewProtocols.files_dropped_on_group.connect(
            self.on_files_dropped_on_group
        )
        self.compare_frame_controller.participant_changed.connect(
            self.signal_tab_controller.on_participant_changed
        )
        self.compare_frame_controller.ui.treeViewProtocols.close_wanted.connect(
            self.on_cfc_close_wanted
        )
        self.compare_frame_controller.show_config_field_types_triggered.connect(
            self.on_show_field_types_config_action_triggered
        )

        self.compare_frame_controller.load_protocol_clicked.connect(
            self.on_compare_frame_controller_load_protocol_clicked
        )
        self.compare_frame_controller.ui.listViewParticipants.doubleClicked.connect(
            self.on_project_settings_action_triggered
        )

        self.ui.lnEdtTreeFilter.textChanged.connect(
            self.on_file_tree_filter_text_changed
        )

        self.ui.tabWidget.currentChanged.connect(self.on_selected_tab_changed)
        self.project_save_timer.timeout.connect(self.save_project)

        self.ui.actionConvert_Folder_to_Project.triggered.connect(
            self.project_manager.convert_folder_to_project
        )
        self.project_manager.project_loaded_status_changed.connect(
            self.on_project_loaded_status_changed
        )
        self.project_manager.project_updated.connect(self.on_project_updated)

        self.ui.textEditProjectDescription.textChanged.connect(
            self.on_text_edit_project_description_text_changed
        )
        self.ui.tabWidget_Project.tabBarDoubleClicked.connect(
            self.on_project_tab_bar_double_clicked
        )

        self.ui.listViewParticipants.doubleClicked.connect(
            self.on_project_settings_action_triggered
        )

        self.ui.actionShowFileTree.triggered.connect(
            self.on_action_show_filetree_triggered
        )
        self.ui.actionShowFileTree.setShortcut(QKeySequence("F10"))

        self.ui.labelNonProjectMode.linkActivated.connect(
            self.on_label_non_project_mode_link_activated
        )

        for i in range(settings.MAX_RECENT_FILE_NR):
            recent_file_action = QAction(self)
            recent_file_action.setVisible(False)
            recent_file_action.triggered.connect(self.on_open_recent_action_triggered)
            self.recentFileActionList.append(recent_file_action)
            self.ui.menuRecent.addAction(self.recentFileActionList[i])

    @staticmethod
    def ensure_zero_margin_layout(container):
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        return layout

    def __setup_embedded_panels(self):
        self.__setup_embedded_waterfall()
        self.__setup_embedded_noise()
        self.refresh_repeat_signal_list()

    def __setup_embedded_waterfall(self):
        if self.embedded_spectrum_controller is not None:
            return

        layout = self.ensure_zero_margin_layout(self.ui.waterfallContainer)
        self.embedded_spectrum_controller = SpectrumDialogController(
            self.project_manager,
            parent=self.ui.waterfallContainer,
            embedded=True,
        )
        self.embedded_spectrum_controller.device_parameters_changed.connect(
            self.project_manager.set_device_parameters
        )
        self.embedded_spectrum_controller.device_parameters_changed.connect(
            self.on_live_device_parameters_changed
        )
        layout.addWidget(self.embedded_spectrum_controller)
        self.embedded_spectrum_controller.show()

    def __setup_embedded_noise(self):
        if self.embedded_noise_dialog is not None:
            return

        layout = self.ensure_zero_margin_layout(self.noiseContainer)
        self.embedded_noise_dialog = GaussianNoiseDialog(
            self.project_manager,
            parent=self.noiseContainer,
            embedded=True,
        )
        self.embedded_noise_dialog.device_parameters_changed.connect(
            self.project_manager.set_device_parameters
        )
        self.embedded_noise_dialog.device_parameters_changed.connect(
            self.on_live_device_parameters_changed
        )
        self.apply_device_parameters_to_dialog(self.embedded_noise_dialog)
        layout.addWidget(self.embedded_noise_dialog)
        self.embedded_noise_dialog.show()

    def __localize_replay_only_ui(self):
        self.ui.menuFile.setTitle(self.tr("Файл"))
        self.ui.menuEdit.setTitle(self.tr("Правка"))
        self.ui.menuHelp.setTitle(self.tr("Справка"))
        self.ui.menuRecent.setTitle(self.tr("Недавние"))
        self.ui.menuDefault_noise_threshold.setTitle(self.tr("Порог шума"))

        self.ui.actionOpen.setText(self.tr("Открыть сигнал..."))
        self.ui.actionOpen_directory.setText(self.tr("Открыть папку..."))
        self.ui.actionRecord.setText(self.tr("Записать сигнал..."))
        self.ui.actionCloseAllFiles.setText(self.tr("Закрыть все сигналы"))
        self.ui.actionExit_App.setText(self.tr("Выход"))
        self.ui.actionOptions.setText(self.tr("Настройки"))
        self.ui.actionShowFileTree.setText(self.tr("Показать файлы"))
        self.ui.actionAbout_AutomaticHacker.setText(
            self.tr("О программе PlutoSDR Protocol Tool")
        )
        self.ui.actionAbout_Qt.setText(self.tr("О Qt"))
        self.ui.lnEdtTreeFilter.setPlaceholderText(self.tr("Поиск файлов"))
        self.ui.labelNonProjectMode.setText(
            self.tr(
                '<html><head/><body><p>Предупреждение: режим проекта отключен. '
                'Настройки сеанса могут не сохраниться после закрытия программы. '
                'Чтобы сохранить конфигурацию, создай проект через Файл -> '
                '<a href="open_new_project_dialog"><span style=" text-decoration: underline;">Новый проект</span></a>. '
                '<a href="dont_show_non_project_again"><span style=" text-decoration: underline;">Больше не показывать</span></a></p></body></html>'
            )
        )

    def get_default_signal_directory(self) -> str:
        directory = FileOperator.get_default_signal_directory(create=True)
        self.signal_source_directory = directory
        FileOperator.RECENT_PATH = directory
        return directory

    def initialize_default_signal_directory(self, load_files=False):
        directory = self.get_default_signal_directory()
        self.update_signal_source_labels()
        self.set_file_tree_root(directory)
        if load_files:
            self.load_signal_files_from_directory(
                directory, show_empty_message=False, set_as_default=True
            )

    def refresh_repeat_signal_list(self):
        signal_frames = [
            frame
            for frame in self.signal_tab_controller.signal_frames
            if frame.signal is not None
        ]

        current_row = self.ui.listWidgetReplaySignals.currentRow()
        self.ui.listWidgetReplaySignals.blockSignals(True)
        self.ui.listWidgetReplaySignals.clear()
        for frame in signal_frames:
            item = QListWidgetItem(frame.ui.lineEditSignalName.text().strip())
            item.setToolTip(frame.signal.filename or frame.ui.lineEditSignalName.text())
            self.ui.listWidgetReplaySignals.addItem(item)
        self.ui.listWidgetReplaySignals.blockSignals(False)

        if not signal_frames:
            self.ui.stackedWidgetRepeat.setCurrentWidget(self.ui.pageRepeatPlaceholder)
            self.close_embedded_repeat_dialog()
            return

        next_row = min(max(current_row, 0), len(signal_frames) - 1)
        self.ui.listWidgetReplaySignals.setCurrentRow(next_row)

    def update_signal_source_labels(self):
        if not self.signal_source_directory:
            self.signal_source_directory = self.get_default_signal_directory()

        if self.signal_source_directory:
            text = "Папка сигналов: {0}".format(self.signal_source_directory)
        else:
            text = "Папка сигналов: не выбрана"

        self.signal_tab_controller.ui.labelSignalFolderPath.setText(text)
        self.ui.labelReplayFolderPath.setText(text)

    def set_file_tree_root(self, path: str):
        if not path:
            path = QDir.homePath()

        self.filemodel.setRootPath(path)
        self.ui.fileTree.setRootIndex(
            self.file_proxy_model.mapFromSource(self.filemodel.index(path))
        )
        self.ui.fileTree.setToolTip(path)

    @classmethod
    def collect_signal_files_from_directory(cls, directory: str) -> list[str]:
        try:
            entries = sorted(os.listdir(directory), key=str.casefold)
        except OSError:
            return []

        result = []
        for entry in entries:
            path = os.path.join(directory, entry)
            if os.path.isfile(path) and entry.lower().endswith(cls.SIGNAL_FILE_SUFFIXES):
                result.append(path)
        return result

    def load_signal_files_from_directory(
        self, directory: str, show_empty_message=True, set_as_default=True
    ):
        self.signal_source_directory = directory
        FileOperator.RECENT_PATH = directory
        if set_as_default:
            FileOperator.set_default_signal_directory(directory)
        self.update_signal_source_labels()
        self.set_file_tree_root(directory)

        signal_files = self.collect_signal_files_from_directory(directory)
        self.close_all_files()

        if not signal_files:
            self.refresh_repeat_signal_list()
            if show_empty_message:
                QMessageBox.information(
                    self,
                    self.tr("Файлы не найдены"),
                    self.tr("В выбранной папке нет поддерживаемых файлов сигналов."),
                )
            return

        self.add_files(signal_files)
        self.ui.tabWidget.setCurrentWidget(self.ui.tab_interpretation)
        self.signal_tab_controller.ui.listWidgetSignals.setCurrentRow(0)
        self.ui.listWidgetReplaySignals.setCurrentRow(0)

    def select_signal_files(self) -> list[str]:
        start_dir = self.signal_source_directory or FileOperator.RECENT_PATH
        name_filter = ";;".join(
            [FileOperator.EVERYTHING_FILE_FILTER]
            + FileOperator.SIGNAL_NAME_FILTERS
            + [FileOperator.COMPRESSED_COMPLEX_FILE_FILTER, FileOperator.WAV_FILE_FILTER]
        )
        filenames, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            self.tr("Выбрать файлы сигналов"),
            start_dir,
            name_filter,
        )
        return filenames

    def close_embedded_repeat_dialog(self):
        if self.embedded_repeat_dialog is None:
            return

        layout = self.ensure_zero_margin_layout(self.ui.repeatContainer)
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)

        self.embedded_repeat_dialog.close()
        self.embedded_repeat_dialog = None

    def show_repeat_dialog_for_frame(self, signal_frame: SignalFrame | None):
        if signal_frame is None or signal_frame.signal is None:
            self.ui.stackedWidgetRepeat.setCurrentWidget(self.ui.pageRepeatPlaceholder)
            self.close_embedded_repeat_dialog()
            return

        self.close_embedded_repeat_dialog()
        layout = self.ensure_zero_margin_layout(self.ui.repeatContainer)
        self.embedded_repeat_dialog = SendDialog(
            self.project_manager,
            modulated_data=signal_frame.signal.iq_array,
            parent=self.ui.repeatContainer,
            embedded=True,
        )
        self.embedded_repeat_dialog.device_parameters_changed.connect(
            self.project_manager.set_device_parameters
        )
        self.apply_device_parameters_to_dialog(self.embedded_repeat_dialog)
        layout.addWidget(self.embedded_repeat_dialog)
        self.embedded_repeat_dialog.show()
        self.ui.stackedWidgetRepeat.setCurrentWidget(self.ui.pageRepeatHost)

    def apply_device_parameters_to_dialog(self, dialog):
        if dialog is None or not hasattr(dialog, "device_settings_widget"):
            return

        widget = dialog.device_settings_widget
        frequency = self.project_manager.device_conf.get("frequency")
        if frequency is not None:
            widget.ui.spinBoxFreq.blockSignals(True)
            widget.ui.spinBoxFreq.setValue(frequency)
            widget.ui.spinBoxFreq.blockSignals(False)
            if getattr(widget, "device", None) is not None:
                widget.device.frequency = frequency

    @pyqtSlot(dict)
    def on_live_device_parameters_changed(self, parameters: dict):
        self.project_manager.set_device_parameters(parameters)
        if self.embedded_repeat_dialog is not None:
            self.apply_device_parameters_to_dialog(self.embedded_repeat_dialog)
        if self.embedded_noise_dialog is not None:
            self.apply_device_parameters_to_dialog(self.embedded_noise_dialog)

    def add_plain_bits_from_txt(self, filename: str):
        logger.info("Text protocol import is disabled in replay-only mode.")

    def __add_empty_frame_for_filename(self, protocol: ProtocolAnalyzer, filename: str):
        sf = self.signal_tab_controller.add_empty_frame(filename, protocol)
        self.signal_protocol_dict[sf] = protocol
        self.set_frame_numbers()
        self.file_proxy_model.open_files.add(filename)

    def add_protocol_file(self, filename):
        logger.info("Protocol import is disabled in replay-only mode.")

    def add_signalfile(
        self, filename: str, group_id=0, enforce_sample_rate=None, signal_timestamp=0
    ):
        if not os.path.exists(filename):
            QMessageBox.critical(
                self,
                self.tr("File not Found"),
                self.tr(
                    "The file {0} could not be found. Was it moved or renamed?"
                ).format(filename),
            )
            return

        sig_name = os.path.splitext(os.path.basename(filename))[0]

        # Use default sample rate for signal
        # Sample rate will be overridden in case of a project later
        if enforce_sample_rate is not None:
            sample_rate = enforce_sample_rate
        else:
            sample_rate = self.project_manager.device_conf["sample_rate"]

        signal = Signal(
            filename, sig_name, sample_rate=sample_rate, timestamp=signal_timestamp
        )

        self.file_proxy_model.open_files.add(filename)
        self.add_signal(signal, group_id)

    def add_signal(self, signal, group_id=0, index=-1):
        self.setCursor(Qt.CursorShape.WaitCursor)
        pa = ProtocolAnalyzer(signal)
        sig_frame = self.signal_tab_controller.add_signal_frame(pa, index=index)
        sig_frame.ui.lineEditSignalName.textChanged.connect(
            self.refresh_repeat_signal_list
        )
        pa = self.compare_frame_controller.add_protocol(pa, group_id)

        signal.blockSignals(True)
        has_entry = self.project_manager.read_project_file_for_signal(signal)

        if (
            self.ui.actionAuto_detect_new_signals.isChecked()
            and not has_entry
            and not signal.changed
        ):
            sig_frame.ui.stackedWidget.setCurrentWidget(sig_frame.ui.pageLoading)
            QApplication.processEvents()
            if not signal.already_demodulated:
                signal.auto_detect(detect_modulation=True, detect_noise=False)
            sig_frame.ui.stackedWidget.setCurrentWidget(sig_frame.ui.pageSignal)

        signal.blockSignals(False)

        self.signal_protocol_dict[sig_frame] = pa

        sig_frame.refresh_signal(draw_full_signal=True)
        sig_frame.refresh_signal_information(block=True)

        QApplication.processEvents()
        sig_frame.show_protocol(refresh=True)

        if self.project_manager.read_participants_for_signal(signal, pa.messages):
            sig_frame.ui.gvSignal.redraw_view()

        sig_frame.ui.gvSignal.auto_fit_view()
        self.set_frame_numbers()
        self.refresh_repeat_signal_list()

        self.compare_frame_controller.filter_search_results()
        self.refresh_main_menu()
        self.unsetCursor()

    def close_protocol(self, protocol):
        self.compare_frame_controller.remove_protocol(protocol)
        protocol.eliminate()

    def close_signal_frame(self, signal_frame: SignalFrame):
        try:
            self.project_manager.write_signal_information_to_project_file(
                signal_frame.signal
            )
            try:
                proto = self.signal_protocol_dict[signal_frame]
            except KeyError:
                proto = None

            if proto is not None:
                self.close_protocol(proto)
                del self.signal_protocol_dict[signal_frame]

            if (
                self.signal_tab_controller.ui.scrlAreaSignals.minimumHeight()
                > signal_frame.height()
            ):
                self.signal_tab_controller.ui.scrlAreaSignals.setMinimumHeight(
                    self.signal_tab_controller.ui.scrlAreaSignals.minimumHeight()
                    - signal_frame.height()
                )

            if signal_frame.signal is not None:
                # Non-Empty Frame (when a signal and not a protocol is opened)
                self.file_proxy_model.open_files.discard(signal_frame.signal.filename)

            self.signal_tab_controller.remove_signal_frame(signal_frame)
            signal_frame.eliminate()

            self.compare_frame_controller.ui.treeViewProtocols.expandAll()
            self.set_frame_numbers()
            self.refresh_repeat_signal_list()
            self.refresh_main_menu()
        except Exception as e:
            Errors.exception(e)
            self.unsetCursor()

    def add_files(self, filepaths, group_id=0, enforce_sample_rate=None):
        num_files = len(filepaths)
        if num_files == 0:
            return

        for i, filename in enumerate(filepaths):
            if not os.path.exists(filename):
                continue

            if os.path.isdir(filename):
                for f in self.signal_tab_controller.signal_frames:
                    self.close_signal_frame(f)

                FileOperator.RECENT_PATH = filename
                self.project_manager.set_project_folder(filename)
                return

            FileOperator.RECENT_PATH = os.path.split(filename)[0]

            if filename.endswith(".complex"):
                self.add_signalfile(
                    filename, group_id, enforce_sample_rate=enforce_sample_rate
                )
            elif filename.endswith(".coco"):
                self.add_signalfile(
                    filename, group_id, enforce_sample_rate=enforce_sample_rate
                )
            elif (
                filename.endswith(".proto")
                or filename.endswith(".proto.xml")
                or filename.endswith(".bin")
            ):
                self.add_protocol_file(filename)
            elif filename.endswith(".wav"):
                try:
                    import wave

                    w = wave.open(filename)
                    w.close()
                except wave.Error as e:
                    Errors.generic_error(
                        "Unsupported WAV type",
                        "Only uncompressed WAVs (PCM) are supported.",
                        str(e),
                    )
                    continue
                self.add_signalfile(
                    filename, group_id, enforce_sample_rate=enforce_sample_rate
                )
            elif filename.endswith(".txt"):
                self.add_plain_bits_from_txt(filename)
            elif filename.endswith(".csv"):
                self.__import_csv(filename, group_id)
                continue
            elif os.path.basename(filename) == settings.PROJECT_FILE:
                self.project_manager.set_project_folder(os.path.split(filename)[0])
            else:
                self.add_signalfile(
                    filename, group_id, enforce_sample_rate=enforce_sample_rate
                )

            if self.project_manager.project_file is None:
                self.adjust_for_current_file(filename)

            self.refresh_main_menu()

    def set_frame_numbers(self):
        self.signal_tab_controller.set_frame_numbers()

    def closeEvent(self, event: QCloseEvent):
        self.close_embedded_repeat_dialog()
        if self.embedded_spectrum_controller is not None:
            self.embedded_spectrum_controller.close()
            self.embedded_spectrum_controller = None
        self.save_project()
        settings.write(
            "{}/geometry".format(self.__class__.__name__), self.saveGeometry()
        )
        super().closeEvent(event)

    def close_all_files(self):
        self.signal_tab_controller.close_all()
        self.compare_frame_controller.reset()

        self.signal_tab_controller.signal_undo_stack.clear()
        self.compare_frame_controller.protocol_undo_stack.clear()

    def show_options_dialog_specific_tab(self, tab_index: int):
        op = OptionsDialog(self.plugin_manager.installed_plugins, parent=self)
        op.values_changed.connect(self.on_options_changed)
        op.ui.tabWidget.setCurrentIndex(tab_index)
        op.show()

    def refresh_main_menu(self):
        enable = len(self.signal_protocol_dict) > 0
        self.ui.actionSaveAllSignals.setEnabled(enable)
        self.ui.actionCloseAllFiles.setEnabled(enable)

    def apply_default_view(self, view_index: int):
        self.compare_frame_controller.ui.cbProtoView.setCurrentIndex(view_index)
        for sig_frame in self.signal_tab_controller.signal_frames:
            sig_frame.ui.cbProtoView.setCurrentIndex(view_index)

    def show_project_settings(self):
        pdc = ProjectDialog(
            new_project=False, project_manager=self.project_manager, parent=self
        )
        pdc.finished.connect(self.on_project_dialog_finished)
        pdc.show()

    def collapse_project_tab_bar(self):
        self.ui.tabParticipants.hide()
        self.ui.tabDescription.hide()
        self.ui.tabWidget_Project.setMaximumHeight(
            self.ui.tabWidget_Project.tabBar().height()
        )

    def expand_project_tab_bar(self):
        self.ui.tabDescription.show()
        self.ui.tabParticipants.show()
        self.ui.tabWidget_Project.setMaximumHeight(9000)

    def save_project(self):
        self.project_manager.save_project()

    def close_project(self):
        self.save_project()
        self.close_all_files()
        self.compare_frame_controller.proto_analyzer.message_types.clear()
        self.compare_frame_controller.active_message_type.clear()
        self.compare_frame_controller.updateUI()
        self.project_manager.participants.clear()
        self.participant_legend_model.update()

        self.filemodel.setRootPath(QDir.homePath())
        self.ui.fileTree.setRootIndex(
            self.file_proxy_model.mapFromSource(self.filemodel.index(QDir.homePath()))
        )
        self.hide_file_tree()

        self.project_manager.project_path = ""
        self.project_manager.project_file = None

    @pyqtSlot()
    def on_project_tab_bar_double_clicked(self):
        if self.ui.tabParticipants.isVisible():
            self.collapse_project_tab_bar()
        else:
            self.expand_project_tab_bar()

    @pyqtSlot()
    def on_project_updated(self):
        self.participant_legend_model.update()
        self.compare_frame_controller.refresh()
        self.ui.textEditProjectDescription.setText(self.project_manager.description)

    @pyqtSlot()
    def on_fullscreen_action_triggered(self):
        if self.ui.actionFullscreen_mode.isChecked():
            self.showFullScreen()
        else:
            self.showMaximized()

    def adjust_for_current_file(self, file_path):
        if file_path is None:
            return

        if file_path in FileOperator.archives.keys():
            file_path = copy.copy(FileOperator.archives[file_path])

        recent_file_paths = settings.read("recentFiles", [], list)
        recent_file_paths = (
            [] if recent_file_paths is None else recent_file_paths
        )  # check None for OSX
        recent_file_paths = [
            p
            for p in recent_file_paths
            if p != file_path and p is not None and os.path.exists(p)
        ]
        recent_file_paths.insert(0, file_path)
        recent_file_paths = recent_file_paths[: settings.MAX_RECENT_FILE_NR]

        self.init_recent_file_action_list(recent_file_paths)

        settings.write("recentFiles", recent_file_paths)

    def init_recent_file_action_list(self, recent_file_paths: list):
        for i in range(len(self.recentFileActionList)):
            self.recentFileActionList[i].setVisible(False)

        if recent_file_paths is None:
            return

        for i, file_path in enumerate(recent_file_paths):
            if os.path.isfile(file_path):
                display_text = os.path.basename(file_path)
                self.recentFileActionList[i].setIcon(QIcon())
            elif os.path.isdir(file_path):
                head, tail = os.path.split(file_path)
                display_text = tail
                head, tail = os.path.split(head)
                if tail:
                    display_text = tail + "/" + display_text

                self.recentFileActionList[i].setIcon(QIcon.fromTheme("folder"))
            else:
                continue

            self.recentFileActionList[i].setText(display_text)
            self.recentFileActionList[i].setData(file_path)
            self.recentFileActionList[i].setVisible(True)

    @pyqtSlot()
    def on_show_field_types_config_action_triggered(self):
        self.show_options_dialog_specific_tab(tab_index=2)

    @pyqtSlot()
    def on_open_recent_action_triggered(self):
        action = self.sender()
        try:
            if os.path.isdir(action.data()):
                self.project_manager.set_project_folder(action.data())
            elif os.path.isfile(action.data()):
                self.setCursor(Qt.CursorShape.WaitCursor)
                self.add_files(
                    FileOperator.uncompress_archives([action.data()], QDir.tempPath())
                )
                self.unsetCursor()
        except Exception as e:
            Errors.exception(e)
            self.unsetCursor()

    @pyqtSlot()
    def on_show_about_clicked(self):
        descr = (
            "<b><h2>PlutoSDR Protocol Tool</h2></b>Version: {0}<br /><br />"
            "Project: Никита Гурачевский, ИА-232<br />"
            "Target hardware: Analog Devices PlutoSDR<br />"
            "Mode: IQ capture and replay only.".format(version.VERSION)
        )

        QMessageBox.about(self, self.tr("About"), self.tr(descr))

    @pyqtSlot(int, int, int, int)
    def show_protocol_selection_in_interpretation(
        self, start_message, start, end_message, end
    ):
        try:
            cfc = self.compare_frame_controller
            msg_total = 0
            last_sig_frame = None
            for protocol in cfc.protocol_list:
                if not protocol.show.value:
                    continue
                n = protocol.num_messages
                view_type = cfc.ui.cbProtoView.currentIndex()
                messages = [
                    i - msg_total
                    for i in range(msg_total, msg_total + n)
                    if start_message <= i <= end_message
                ]
                if len(messages) > 0:
                    try:
                        signal_frame = next(
                            (
                                sf
                                for sf, pf in self.signal_protocol_dict.items()
                                if pf == protocol
                            )
                        )
                    except StopIteration:
                        QMessageBox.critical(
                            self,
                            self.tr("Error"),
                            self.tr("Could not find corresponding signal frame."),
                        )
                        return
                    signal_frame.set_roi_from_protocol_analysis(
                        min(messages), start, max(messages), end + 1, view_type
                    )
                    last_sig_frame = signal_frame
                msg_total += n
            focus_frame = last_sig_frame
            if last_sig_frame is not None:
                self.signal_tab_controller.ui.scrollArea.ensureWidgetVisible(
                    last_sig_frame, 0, 0
                )

            QApplication.processEvents()
            self.ui.tabWidget.setCurrentWidget(self.ui.tab_interpretation)
            if focus_frame is not None:
                self.signal_tab_controller.select_signal_frame(focus_frame)
                focus_frame.ui.txtEdProto.setFocus()
        except Exception as e:
            logger.exception(e)

    @pyqtSlot(str)
    def on_file_tree_filter_text_changed(self, text: str):
        if len(text) > 0:
            self.filemodel.setNameFilters(["*" + text + "*"])
        else:
            self.filemodel.setNameFilters(["*"])

    @pyqtSlot()
    def update_decodings(self):
        self.project_manager.load_decodings()
        self.compare_frame_controller.fill_decoding_combobox()
        self.compare_frame_controller.refresh_existing_encodings()

    @pyqtSlot(int)
    def on_selected_tab_changed(self, index: int):
        if self.ui.tabWidget.widget(index) == self.ui.tab_interpretation:
            self.undo_group.setActiveStack(self.signal_tab_controller.signal_undo_stack)

    @pyqtSlot()
    def on_show_record_dialog_action_triggered(self):
        pm = self.project_manager
        try:
            r = ReceiveDialog(pm, parent=self)
        except OSError as e:
            logger.error(repr(e))
            return

        if r.has_empty_device_list:
            Errors.no_device()
            r.close()
            return

        r.device_parameters_changed.connect(pm.set_device_parameters)
        self.apply_device_parameters_to_dialog(r)
        r.files_recorded.connect(self.on_signals_recorded)
        r.show()

    def create_protocol_sniff_dialog(self, testing_mode=False):
        pm = self.project_manager
        signal = next(
            (proto.signal for proto in self.compare_frame_controller.protocol_list),
            None,
        )
        signals = [
            f.signal for f in self.signal_tab_controller.signal_frames if f.signal
        ]

        psd = ProtocolSniffDialog(
            project_manager=pm,
            signal=signal,
            signals=signals,
            testing_mode=testing_mode,
            parent=self,
        )

        if psd.has_empty_device_list:
            Errors.no_device()
            psd.close()
            return None
        else:
            psd.device_parameters_changed.connect(pm.set_device_parameters)
            psd.protocol_accepted.connect(
                self.compare_frame_controller.add_sniffed_protocol_messages
            )
            return psd

    @pyqtSlot()
    def show_proto_sniff_dialog(self):
        psd = self.create_protocol_sniff_dialog()
        if psd:
            psd.show()

    @pyqtSlot()
    def on_show_spectrum_dialog_action_triggered(self):
        pm = self.project_manager
        r = SpectrumDialogController(pm, parent=self)
        if r.has_empty_device_list:
            Errors.no_device()
            r.close()
            return

        r.device_parameters_changed.connect(pm.set_device_parameters)
        r.show()

    @pyqtSlot(list)
    def on_signals_recorded(self, recorded_files: list):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        if recorded_files:
            directory = os.path.dirname(recorded_files[0].filename)
            self.load_signal_files_from_directory(
                directory, show_empty_message=False, set_as_default=True
            )
            metadata_by_filename = {
                recorded_file.filename: recorded_file for recorded_file in recorded_files
            }
            for frame in self.signal_tab_controller.signal_frames:
                if frame.signal is None:
                    continue
                recorded_file = metadata_by_filename.get(frame.signal.filename)
                if recorded_file is None:
                    continue
                frame.signal.sample_rate = recorded_file.sample_rate
                frame.signal.timestamp = recorded_file.timestamp
            last_recorded_file = recorded_files[-1].filename
            for index, frame in enumerate(self.signal_tab_controller.signal_frames):
                if (
                    frame.signal is not None
                    and frame.signal.filename == last_recorded_file
                ):
                    self.signal_tab_controller.ui.listWidgetSignals.setCurrentRow(index)
                    self.ui.listWidgetReplaySignals.setCurrentRow(index)
                    break
        QApplication.restoreOverrideCursor()

    @pyqtSlot()
    def show_options_dialog_action_triggered(self):
        self.show_options_dialog_specific_tab(tab_index=4)

    @pyqtSlot()
    def on_new_project_action_triggered(self):
        pdc = ProjectDialog(parent=self)
        pdc.finished.connect(self.on_project_dialog_finished)
        pdc.show()

    @pyqtSlot()
    def on_project_settings_action_triggered(self):
        self.show_project_settings()

    @pyqtSlot()
    def on_edit_menu_about_to_show(self):
        self.ui.actionShowFileTree.setChecked(self.ui.splitter.sizes()[0] > 0)

    def hide_file_tree(self):
        self.ui.splitter.setSizes([0, 1])

    @pyqtSlot()
    def on_action_show_filetree_triggered(self):
        if self.ui.splitter.sizes()[0] > 0:
            self.hide_file_tree()
        else:
            self.ui.splitter.setSizes([1, 1])

    @pyqtSlot()
    def on_project_dialog_finished(self):
        if self.sender().committed:
            if self.sender().new_project:
                self.close_project()
                self.project_manager.from_dialog(self.sender())
            else:
                self.project_manager.project_updated.emit()

    @pyqtSlot()
    def on_open_file_action_triggered(self):
        self.on_open_signal_files_requested()

    @pyqtSlot()
    def on_open_signal_files_requested(self):
        filenames = self.select_signal_files()
        if not filenames:
            return

        directory = os.path.dirname(filenames[0])
        self.signal_source_directory = directory
        FileOperator.set_default_signal_directory(directory)
        FileOperator.RECENT_PATH = directory
        self.update_signal_source_labels()
        self.set_file_tree_root(directory)

        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            file_names = FileOperator.uncompress_archives(filenames, QDir.tempPath())
            self.add_files(file_names)
        except Exception as e:
            Errors.exception(e)
        finally:
            self.unsetCursor()

    @pyqtSlot()
    def on_choose_signal_folder_requested(self):
        start_dir = self.signal_source_directory or self.get_default_signal_directory()
        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("Выбрать папку с сигналами"),
            start_dir,
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks,
        )
        if not directory:
            return

        self.load_signal_files_from_directory(directory)

    @pyqtSlot(int)
    def on_replay_signal_list_current_row_changed(self, row: int):
        signal_frames = [
            frame
            for frame in self.signal_tab_controller.signal_frames
            if frame.signal is not None
        ]
        if 0 <= row < len(signal_frames):
            selected_frame = signal_frames[row]
            self.signal_tab_controller.select_signal_frame(selected_frame)
            self.show_repeat_dialog_for_frame(selected_frame)
        else:
            self.show_repeat_dialog_for_frame(None)

    @pyqtSlot()
    def on_open_directory_action_triggered(self):
        self.show_open_dialog(directory=True)

    def show_open_dialog(self, directory=False):
        if not directory:
            self.on_open_signal_files_requested()
            return

        chosen_dir = QFileDialog.getExistingDirectory(
            self,
            self.tr("Открыть папку"),
            FileOperator.RECENT_PATH,
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks,
        )
        if not chosen_dir:
            return

        try:
            for f in self.signal_tab_controller.signal_frames:
                self.close_signal_frame(f)

            self.project_manager.set_project_folder(chosen_dir)
        except Exception as e:
            Errors.exception(e)

    @pyqtSlot()
    def on_close_all_files_action_triggered(self):
        self.close_all_files()

    @pyqtSlot(list)
    def on_files_dropped(self, files):
        """
        :type files: list of QtCore.QUrl
        """
        self.__add_urls_to_group(files, group_id=0)

    @pyqtSlot(list, int)
    def on_files_dropped_on_group(self, files, group_id: int):
        """
        :param group_id:
        :type files: list of QtCore.QUrl
        """
        self.__add_urls_to_group(files, group_id=group_id)

    def __add_urls_to_group(self, file_urls, group_id=0):
        local_files = [
            file_url.toLocalFile() for file_url in file_urls if file_url.isLocalFile()
        ]
        if len(local_files) > 0:
            self.setCursor(Qt.CursorShape.WaitCursor)
            self.add_files(
                FileOperator.uncompress_archives(local_files, QDir.tempPath()),
                group_id=group_id,
            )
            self.unsetCursor()

    @pyqtSlot(list)
    def on_cfc_close_wanted(self, protocols: list):
        frame_protos = {
            sframe: protocol
            for sframe, protocol in self.signal_protocol_dict.items()
            if protocol in protocols
        }

        for frame in frame_protos:
            self.close_signal_frame(frame)

        for proto in (
            proto for proto in protocols if proto not in frame_protos.values()
        ):
            # close protocols without associated signal frame
            self.close_protocol(proto)

    @pyqtSlot(dict)
    def on_options_changed(self, changed_options: dict):
        refresh_protocol_needed = "show_pause_as_time" in changed_options

        if refresh_protocol_needed:
            for sf in self.signal_tab_controller.signal_frames:
                sf.refresh_protocol()

        self.project_manager.reload_field_types()

        self.compare_frame_controller.refresh_field_types_for_labels()
        self.compare_frame_controller.set_shown_protocols()

        if "num_sending_repeats" in changed_options:
            self.project_manager.device_conf["num_sending_repeats"] = changed_options[
                "num_sending_repeats"
            ]

        if "default_view" in changed_options:
            self.apply_default_view(int(changed_options["default_view"]))

        if "spectrogram_colormap" in changed_options:
            self.signal_tab_controller.redraw_spectrograms()

    @pyqtSlot()
    def on_text_edit_project_description_text_changed(self):
        self.project_manager.description = (
            self.ui.textEditProjectDescription.toPlainText()
        )

    @pyqtSlot()
    def on_btn_file_tree_go_up_clicked(self):
        cur_dir = self.filemodel.rootDirectory()
        if cur_dir.cdUp():
            path = cur_dir.path()
            self.filemodel.setRootPath(path)
            self.ui.fileTree.setRootIndex(
                self.file_proxy_model.mapFromSource(self.filemodel.index(path))
            )

    @pyqtSlot(int, Signal)
    def on_signal_created(self, index: int, signal: Signal):
        self.add_signal(signal, index=index)

    @pyqtSlot()
    def on_cancel_triggered(self):
        for signal_frame in self.signal_tab_controller.signal_frames:
            signal_frame.cancel_filtering()

    @pyqtSlot()
    def on_import_samples_from_csv_action_triggered(self):
        self.__import_csv(file_name="")

    @pyqtSlot(bool)
    def on_auto_detect_new_signals_action_triggered(self, checked: bool):
        settings.write("auto_detect_new_signals", bool(checked))

    def __import_csv(self, file_name, group_id=0):
        logger.info("CSV import is disabled in replay-only mode.")

    @pyqtSlot(str)
    def on_label_non_project_mode_link_activated(self, link: str):
        if link == "dont_show_non_project_again":
            self.ui.labelNonProjectMode.hide()
            settings.write("show_non_project_warning", False)
        elif link == "open_new_project_dialog":
            self.on_new_project_action_triggered()

    @pyqtSlot(bool)
    def on_project_loaded_status_changed(self, project_loaded: bool):
        self.ui.actionProject_settings.setVisible(project_loaded)
        self.ui.actionSave_project.setVisible(project_loaded)
        self.ui.actionClose_project.setVisible(project_loaded)
        self.ui.actionConvert_Folder_to_Project.setDisabled(project_loaded)
        self.__set_non_project_warning_visibility()

    @pyqtSlot()
    def on_compare_frame_controller_load_protocol_clicked(self):
        dialog = FileOperator.get_open_dialog(
            directory_mode=False, parent=self, name_filter="proto"
        )
        if dialog.exec():
            for filename in dialog.selectedFiles():
                self.add_protocol_file(filename)

    @pyqtSlot()
    def on_action_automatic_noise_threshold_triggered(self):
        settings.write("default_noise_threshold", "automatic")

    @pyqtSlot()
    def on_action_1_noise_threshold_triggered(self):
        settings.write("default_noise_threshold", "1")

    @pyqtSlot()
    def on_action_5_noise_threshold_triggered(self):
        settings.write("default_noise_threshold", "5")

    @pyqtSlot()
    def on_action_10_noise_threshold_triggered(self):
        settings.write("default_noise_threshold", "10")

    @pyqtSlot()
    def on_action_100_noise_threshold_triggered(self):
        settings.write("default_noise_threshold", "100")
