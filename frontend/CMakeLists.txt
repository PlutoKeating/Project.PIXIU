cmake_minimum_required(VERSION 3.10)

project(pixiu-frontend VERSION 0.1.0 LANGUAGES CXX)

option(PIXIU_HAVE_KYSDK "Build with KylinSDK integration" OFF)
option(PIXIU_HAVE_QRENCODE "Build QR pairing rendering with libqrencode" ON)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt5 5.9 REQUIRED COMPONENTS Widgets Network WebSockets Test)

add_executable(pixiu-frontend
    src/main.cpp
    src/app/PixiuApp.h
    src/app/PixiuApp.cpp
    src/app/SingleInstanceGuard.h
    src/app/SingleInstanceGuard.cpp
    src/app/TrayIcon.h
    src/app/TrayIcon.cpp
    src/app/AppSettings.h
    src/app/AppSettings.cpp
    src/app/MonitorController.h
    src/app/MonitorController.cpp
    src/app/ShortcutManager.h
    src/app/ShortcutManager.cpp
    src/app/QueryController.h
    src/app/QueryController.cpp
    src/app/WriteController.h
    src/app/WriteController.cpp
    src/widgets/FloatingBall.h
    src/widgets/FloatingBall.cpp
    src/widgets/ChatWindow.h
    src/widgets/ChatWindow.cpp
    src/widgets/InputBar.h
    src/widgets/InputBar.cpp
    src/widgets/MessageList.h
    src/widgets/MessageList.cpp
    src/widgets/ThinkingSkeleton.h
    src/widgets/ThinkingSkeleton.cpp
    src/widgets/EvidenceCard.h
    src/widgets/EvidenceCard.cpp
    src/widgets/EvidenceDetailDialog.h
    src/widgets/EvidenceDetailDialog.cpp
    src/widgets/ImportDialog.h
    src/widgets/ImportDialog.cpp
    src/models/ChatMessage.h
    src/models/MemoryAtom.h
    src/services/BackendTypes.h
    src/services/BackendTransport.h
    src/services/BackendTransport.cpp
    src/services/HttpBackendTransport.h
    src/services/HttpBackendTransport.cpp
    src/services/WebSocketClient.h
    src/services/WebSocketClient.cpp
    src/services/NotifyService.h
    src/services/NotifyService.cpp
    src/app/ForgetController.h
    src/app/ForgetController.cpp
    src/widgets/ForgetDialog.h
    src/widgets/ForgetDialog.cpp
    src/widgets/MemoryPanel.h
    src/widgets/MemoryPanel.cpp
    src/widgets/MonitorCenterDialog.h
    src/widgets/MonitorCenterDialog.cpp
    src/widgets/PairDialog.h
    src/widgets/PairDialog.cpp
    src/widgets/SettingsDialog.h
    src/widgets/SettingsDialog.cpp
    src/app/ConflictController.h
    src/app/ConflictController.cpp
    src/app/PreferenceController.h
    src/app/PreferenceController.cpp
    src/app/SyncController.h
    src/app/SyncController.cpp
    src/app/EventRouter.h
    src/app/EventRouter.cpp
    src/app/ThemeService.h
    src/app/ThemeService.cpp
    src/app/UkuiWindow.h
    src/app/UkuiWindow.cpp
    resources/resources.qrc
)

target_link_libraries(pixiu-frontend
    PRIVATE
        Qt5::Widgets
        Qt5::Network
        Qt5::WebSockets
)

target_include_directories(pixiu-frontend
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)

include(GNUInstallDirs)
install(TARGETS pixiu-frontend
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(FILES resources/com.kylin.pixiu.desktop
    DESTINATION ${CMAKE_INSTALL_DATADIR}/applications
)
install(FILES resources/icons/pixiu.svg
    DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps
)

if(PIXIU_HAVE_QRENCODE)
    # 配对二维码渲染：libqrencode 可选依赖，缺失时 PairDialog 降级为令牌文本。
    find_library(QRENCODE_LIBRARY NAMES qrencode)
    if(QRENCODE_LIBRARY)
        target_compile_definitions(pixiu-frontend PRIVATE PIXIU_HAVE_QRENCODE=1)
        target_link_libraries(pixiu-frontend PRIVATE ${QRENCODE_LIBRARY})
        message(STATUS "libqrencode found: QR pairing rendering enabled")
    else()
        message(STATUS "libqrencode not found: QR pairing falls back to token text")
    endif()
endif()

if(PIXIU_HAVE_KYSDK)
    # Phase 7：麒麟桌面能力适配。当前接入 kysdk-shortcut（全局快捷键）与
    # kysdk-notification（桌面通知）。
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(KYSDK_SHORTCUT REQUIRED kysdk-shortcut)
    pkg_check_modules(KYSDK_NOTIFY REQUIRED kysdk-notification)
    pkg_check_modules(KYSDK_QTWIDGETS REQUIRED kysdk-qtwidgets)
    pkg_check_modules(KYSDK_QGSETTINGS REQUIRED gsettings-qt)
    target_compile_definitions(pixiu-frontend PRIVATE PIXIU_HAVE_KYSDK=1)
    target_include_directories(pixiu-frontend PRIVATE
        ${KYSDK_SHORTCUT_INCLUDE_DIRS}
        ${KYSDK_NOTIFY_INCLUDE_DIRS}
        ${KYSDK_QTWIDGETS_INCLUDE_DIRS}
        ${KYSDK_QGSETTINGS_INCLUDE_DIRS}
    )
    target_link_libraries(pixiu-frontend PRIVATE
        ${KYSDK_SHORTCUT_LIBRARIES}
        ${KYSDK_NOTIFY_LIBRARIES}
        ${KYSDK_QTWIDGETS_LIBRARIES}
        ${KYSDK_QGSETTINGS_LIBRARIES}
    )
endif()

# ─── 测试（Qt Test，offscreen 平台运行）──────────────────────
include(CTest)

if(BUILD_TESTING)
    add_executable(t_websocket_client
        tests/t_websocket_client.cpp
        src/services/BackendTypes.h
        src/services/WebSocketClient.h
        src/services/WebSocketClient.cpp
    )
    target_include_directories(t_websocket_client PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_websocket_client PRIVATE Qt5::Test Qt5::WebSockets)
    add_test(NAME websocket_client COMMAND t_websocket_client)

    add_executable(t_http_backend
        tests/t_http_backend.cpp
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
        src/services/HttpBackendTransport.h
        src/services/HttpBackendTransport.cpp
    )
    target_include_directories(t_http_backend PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_http_backend PRIVATE Qt5::Test Qt5::Network)
    add_test(NAME http_backend COMMAND t_http_backend)

    add_executable(t_contract_fixtures
        tests/t_contract_fixtures.cpp
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
        src/services/HttpBackendTransport.h
        src/services/HttpBackendTransport.cpp
    )
    target_include_directories(t_contract_fixtures PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_contract_fixtures PRIVATE Qt5::Test Qt5::Network)
    add_test(NAME contract_fixtures COMMAND t_contract_fixtures)

    add_executable(t_floating_ball
        tests/t_floating_ball.cpp
        src/widgets/FloatingBall.h
        src/widgets/FloatingBall.cpp
    )
    target_include_directories(t_floating_ball PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_floating_ball PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME floating_ball COMMAND t_floating_ball)

    add_executable(t_notify_service
        tests/t_notify_service.cpp
        src/services/NotifyService.h
        src/services/NotifyService.cpp
    )
    target_include_directories(t_notify_service PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_notify_service PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME notify_service COMMAND t_notify_service)

    add_executable(t_forget_controller
        tests/t_forget_controller.cpp
        src/app/ForgetController.h
        src/app/ForgetController.cpp
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
    )
    target_include_directories(t_forget_controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_forget_controller PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME forget_controller COMMAND t_forget_controller)

    add_executable(t_forget_dialog
        tests/t_forget_dialog.cpp
        src/widgets/ForgetDialog.h
        src/widgets/ForgetDialog.cpp
    )
    target_include_directories(t_forget_dialog PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_forget_dialog PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME forget_dialog COMMAND t_forget_dialog)

    add_executable(t_memory_panel
        tests/t_memory_panel.cpp
        src/widgets/MemoryPanel.h
        src/widgets/MemoryPanel.cpp
        src/widgets/PairDialog.h
        src/widgets/PairDialog.cpp
    )
    target_include_directories(t_memory_panel PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_memory_panel PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME memory_panel COMMAND t_memory_panel)

    add_executable(t_pair_dialog
        tests/t_pair_dialog.cpp
        src/widgets/PairDialog.h
        src/widgets/PairDialog.cpp
    )
    target_include_directories(t_pair_dialog PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_pair_dialog PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME pair_dialog COMMAND t_pair_dialog)
    set_tests_properties(pair_dialog PROPERTIES
        ENVIRONMENT "QT_QPA_PLATFORM=offscreen")

    add_executable(t_settings_dialog
        tests/t_settings_dialog.cpp
        src/widgets/SettingsDialog.h
        src/widgets/SettingsDialog.cpp
    )
    target_include_directories(t_settings_dialog PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_settings_dialog PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME settings_dialog COMMAND t_settings_dialog)
    set_tests_properties(settings_dialog PROPERTIES
        ENVIRONMENT "QT_QPA_PLATFORM=offscreen")

    add_executable(t_sync_controller
        tests/t_sync_controller.cpp
        src/app/SyncController.h
        src/app/SyncController.cpp
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
    )
    target_include_directories(t_sync_controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_sync_controller PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME sync_controller COMMAND t_sync_controller)
    set_tests_properties(sync_controller PROPERTIES
        ENVIRONMENT "QT_QPA_PLATFORM=offscreen")

    add_executable(t_event_router
        tests/t_event_router.cpp
        src/app/EventRouter.h
        src/app/EventRouter.cpp
    )
    target_include_directories(t_event_router PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_event_router PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME event_router COMMAND t_event_router)
    set_tests_properties(event_router PROPERTIES
        ENVIRONMENT "QT_QPA_PLATFORM=offscreen")

    add_executable(t_app_icon
        tests/t_app_icon.cpp
        resources/resources.qrc
    )
    target_include_directories(t_app_icon PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_app_icon PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME app_icon COMMAND t_app_icon)
    set_tests_properties(app_icon PROPERTIES
        ENVIRONMENT "QT_QPA_PLATFORM=offscreen")

    add_executable(t_conflict_controller
        tests/t_conflict_controller.cpp
        src/app/ConflictController.h
        src/app/ConflictController.cpp
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
    )
    target_include_directories(t_conflict_controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_conflict_controller PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME conflict_controller COMMAND t_conflict_controller)

    add_executable(t_preference_controller
        tests/t_preference_controller.cpp
        src/app/PreferenceController.h
        src/app/PreferenceController.cpp
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
    )
    target_include_directories(t_preference_controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_preference_controller PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME preference_controller COMMAND t_preference_controller)

    # 快捷键测试始终编译 Qt 降级路径（不注入 PIXIU_HAVE_KYSDK 宏）：
    # kysdk 全局快捷键依赖桌面会话，无法在 offscreen 测试中确定性断言；
    # KYSDK 路径由 PIXIU_HAVE_KYSDK=ON 的应用构建与冒烟验证覆盖。
    add_executable(t_shortcut_manager
        tests/t_shortcut_manager.cpp
        src/app/ShortcutManager.h
        src/app/ShortcutManager.cpp
    )
    target_include_directories(t_shortcut_manager PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_shortcut_manager PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME shortcut_manager COMMAND t_shortcut_manager)

    add_executable(t_theme_service
        tests/t_theme_service.cpp
        src/app/ThemeService.h
        src/app/ThemeService.cpp
    )
    target_include_directories(t_theme_service PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_theme_service PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME theme_service COMMAND t_theme_service)

    add_executable(t_ukui_window
        tests/t_ukui_window.cpp
        src/app/UkuiWindow.h
        src/app/UkuiWindow.cpp
    )
    target_include_directories(t_ukui_window PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_ukui_window PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME ukui_window COMMAND t_ukui_window)

    add_executable(t_memory_atom
        tests/t_memory_atom.cpp
        src/models/MemoryAtom.h
    )
    target_include_directories(t_memory_atom PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_memory_atom PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME memory_atom COMMAND t_memory_atom)

    add_executable(t_query_controller
        tests/t_query_controller.cpp
        src/app/QueryController.h
        src/app/QueryController.cpp
        src/models/MemoryAtom.h
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
    )
    target_include_directories(t_query_controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_query_controller PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME query_controller COMMAND t_query_controller)

    add_executable(t_write_controller
        tests/t_write_controller.cpp
        src/app/WriteController.h
        src/app/WriteController.cpp
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
    )
    target_include_directories(t_write_controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_write_controller PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME write_controller COMMAND t_write_controller)

    add_executable(t_app_settings
        tests/t_app_settings.cpp
        src/app/AppSettings.h
        src/app/AppSettings.cpp
    )
    target_include_directories(t_app_settings PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_app_settings PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME app_settings COMMAND t_app_settings)

    add_executable(t_monitor_controller
        tests/t_monitor_controller.cpp
        src/app/AppSettings.h
        src/app/AppSettings.cpp
        src/app/MonitorController.h
        src/app/MonitorController.cpp
    )
    target_include_directories(t_monitor_controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_monitor_controller PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME monitor_controller COMMAND t_monitor_controller)

    add_executable(t_monitor_center
        tests/t_monitor_center.cpp
        src/app/AppSettings.h
        src/app/AppSettings.cpp
        src/app/MonitorController.h
        src/app/MonitorController.cpp
        src/widgets/MonitorCenterDialog.h
        src/widgets/MonitorCenterDialog.cpp
    )
    target_include_directories(t_monitor_center PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_monitor_center PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME monitor_center COMMAND t_monitor_center)

    add_executable(t_chat_window
        tests/t_chat_window.cpp
        src/widgets/ChatWindow.h
        src/widgets/ChatWindow.cpp
        src/widgets/InputBar.h
        src/widgets/InputBar.cpp
        src/widgets/MessageList.h
        src/widgets/MessageList.cpp
        src/widgets/ThinkingSkeleton.h
        src/widgets/ThinkingSkeleton.cpp
        src/widgets/EvidenceCard.h
        src/widgets/EvidenceCard.cpp
        src/models/ChatMessage.h
        src/services/BackendTypes.h
        src/app/UkuiWindow.h
        src/app/UkuiWindow.cpp
    )
    target_include_directories(t_chat_window PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_chat_window PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME chat_window COMMAND t_chat_window)

    add_executable(t_input_bar
        tests/t_input_bar.cpp
        src/widgets/InputBar.h
        src/widgets/InputBar.cpp
    )
    target_include_directories(t_input_bar PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_input_bar PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME input_bar COMMAND t_input_bar)

    add_executable(t_message_list
        tests/t_message_list.cpp
        src/widgets/MessageList.h
        src/widgets/MessageList.cpp
        src/widgets/ThinkingSkeleton.h
        src/widgets/ThinkingSkeleton.cpp
        src/widgets/EvidenceCard.h
        src/widgets/EvidenceCard.cpp
        src/models/ChatMessage.h
    )
    target_include_directories(t_message_list PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_message_list PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME message_list COMMAND t_message_list)

    add_executable(t_import_dialog
        tests/t_import_dialog.cpp
        src/widgets/ImportDialog.h
        src/widgets/ImportDialog.cpp
    )
    target_include_directories(t_import_dialog PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_import_dialog PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME import_dialog COMMAND t_import_dialog)

    add_executable(t_evidence_card
        tests/t_evidence_card.cpp
        src/widgets/EvidenceCard.h
        src/widgets/EvidenceCard.cpp
    )
    target_include_directories(t_evidence_card PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_evidence_card PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME evidence_card COMMAND t_evidence_card)

    add_executable(t_i18n
        tests/t_i18n.cpp
        resources/resources.qrc
    )
    target_include_directories(t_i18n PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_i18n PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME i18n COMMAND t_i18n)

    add_executable(t_app_navigation
        tests/t_app_navigation.cpp
        src/app/PixiuApp.h
        src/app/PixiuApp.cpp
        src/app/SingleInstanceGuard.h
        src/app/SingleInstanceGuard.cpp
        src/app/TrayIcon.h
        src/app/TrayIcon.cpp
        src/app/AppSettings.h
        src/app/AppSettings.cpp
        src/app/MonitorController.h
        src/app/MonitorController.cpp
        src/app/ShortcutManager.h
        src/app/ShortcutManager.cpp
        src/app/QueryController.h
        src/app/QueryController.cpp
        src/app/WriteController.h
        src/app/WriteController.cpp
        src/widgets/FloatingBall.h
        src/widgets/FloatingBall.cpp
        src/widgets/ChatWindow.h
        src/widgets/ChatWindow.cpp
        src/widgets/InputBar.h
        src/widgets/InputBar.cpp
        src/widgets/MessageList.h
        src/widgets/MessageList.cpp
        src/widgets/ThinkingSkeleton.h
        src/widgets/ThinkingSkeleton.cpp
        src/widgets/EvidenceCard.h
        src/widgets/EvidenceCard.cpp
        src/widgets/EvidenceDetailDialog.h
        src/widgets/EvidenceDetailDialog.cpp
        src/widgets/ImportDialog.h
        src/widgets/ImportDialog.cpp
        src/models/ChatMessage.h
        src/models/MemoryAtom.h
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
        src/services/HttpBackendTransport.h
        src/services/HttpBackendTransport.cpp
        src/services/WebSocketClient.h
        src/services/WebSocketClient.cpp
        src/services/NotifyService.h
        src/services/NotifyService.cpp
        src/app/ForgetController.h
        src/app/ForgetController.cpp
        src/widgets/ForgetDialog.h
        src/widgets/ForgetDialog.cpp
        src/widgets/MemoryPanel.h
        src/widgets/MemoryPanel.cpp
        src/widgets/MonitorCenterDialog.h
        src/widgets/MonitorCenterDialog.cpp
        src/widgets/PairDialog.h
        src/widgets/PairDialog.cpp
        src/widgets/SettingsDialog.h
        src/widgets/SettingsDialog.cpp
        src/app/ConflictController.h
        src/app/ConflictController.cpp
        src/app/PreferenceController.h
        src/app/PreferenceController.cpp
        src/app/SyncController.h
        src/app/SyncController.cpp
        src/app/EventRouter.h
        src/app/EventRouter.cpp
        src/app/ThemeService.h
        src/app/ThemeService.cpp
        src/app/UkuiWindow.h
        src/app/UkuiWindow.cpp
        resources/resources.qrc
    )
    target_include_directories(t_app_navigation PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_app_navigation
        PRIVATE
            Qt5::Test
            Qt5::Widgets
            Qt5::Network
            Qt5::WebSockets
    )
    add_test(NAME app_navigation COMMAND t_app_navigation)

    add_executable(t_window_restore
        tests/t_window_restore.cpp
        src/app/PixiuApp.h
        src/app/PixiuApp.cpp
        src/app/SingleInstanceGuard.h
        src/app/SingleInstanceGuard.cpp
        src/app/TrayIcon.h
        src/app/TrayIcon.cpp
        src/app/AppSettings.h
        src/app/AppSettings.cpp
        src/app/MonitorController.h
        src/app/MonitorController.cpp
        src/app/ShortcutManager.h
        src/app/ShortcutManager.cpp
        src/app/QueryController.h
        src/app/QueryController.cpp
        src/app/WriteController.h
        src/app/WriteController.cpp
        src/widgets/FloatingBall.h
        src/widgets/FloatingBall.cpp
        src/widgets/ChatWindow.h
        src/widgets/ChatWindow.cpp
        src/widgets/InputBar.h
        src/widgets/InputBar.cpp
        src/widgets/MessageList.h
        src/widgets/MessageList.cpp
        src/widgets/ThinkingSkeleton.h
        src/widgets/ThinkingSkeleton.cpp
        src/widgets/EvidenceCard.h
        src/widgets/EvidenceCard.cpp
        src/widgets/EvidenceDetailDialog.h
        src/widgets/EvidenceDetailDialog.cpp
        src/widgets/ImportDialog.h
        src/widgets/ImportDialog.cpp
        src/models/ChatMessage.h
        src/models/MemoryAtom.h
        src/services/BackendTypes.h
        src/services/BackendTransport.h
        src/services/BackendTransport.cpp
        src/services/HttpBackendTransport.h
        src/services/HttpBackendTransport.cpp
        src/services/WebSocketClient.h
        src/services/WebSocketClient.cpp
        src/services/NotifyService.h
        src/services/NotifyService.cpp
        src/app/ForgetController.h
        src/app/ForgetController.cpp
        src/widgets/ForgetDialog.h
        src/widgets/ForgetDialog.cpp
        src/widgets/MemoryPanel.h
        src/widgets/MemoryPanel.cpp
        src/widgets/MonitorCenterDialog.h
        src/widgets/MonitorCenterDialog.cpp
        src/widgets/PairDialog.h
        src/widgets/PairDialog.cpp
        src/widgets/SettingsDialog.h
        src/widgets/SettingsDialog.cpp
        src/app/ConflictController.h
        src/app/ConflictController.cpp
        src/app/PreferenceController.h
        src/app/PreferenceController.cpp
        src/app/SyncController.h
        src/app/SyncController.cpp
        src/app/EventRouter.h
        src/app/EventRouter.cpp
        src/app/ThemeService.h
        src/app/ThemeService.cpp
        src/app/UkuiWindow.h
        src/app/UkuiWindow.cpp
        resources/resources.qrc
    )
    target_include_directories(t_window_restore PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_window_restore
        PRIVATE
            Qt5::Test
            Qt5::Widgets
            Qt5::Network
            Qt5::WebSockets
    )
    add_test(NAME window_restore COMMAND t_window_restore)

    set_tests_properties(websocket_client floating_ball notify_service
        forget_controller forget_dialog memory_panel conflict_controller
        preference_controller shortcut_manager theme_service ukui_window
        memory_atom query_controller write_controller app_settings
        chat_window input_bar message_list import_dialog evidence_card i18n
        sync_controller event_router settings_dialog
        app_navigation window_restore monitor_controller monitor_center
        PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endif()
