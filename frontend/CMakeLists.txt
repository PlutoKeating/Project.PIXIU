cmake_minimum_required(VERSION 3.10)

project(pixiu-frontend VERSION 0.1.0 LANGUAGES CXX)

option(PIXIU_HAVE_KYSDK "Build with KylinSDK integration" OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

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
    src/widgets/EvidenceCard.h
    src/widgets/EvidenceCard.cpp
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
    src/app/ConflictController.h
    src/app/ConflictController.cpp
    src/app/PreferenceController.h
    src/app/PreferenceController.cpp
    src/app/ThemeService.h
    src/app/ThemeService.cpp
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

if(PIXIU_HAVE_KYSDK)
    # Phase 7：麒麟桌面能力适配。当前接入 kysdk-shortcut（全局快捷键）与
    # kysdk-notification（桌面通知）。
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(KYSDK_SHORTCUT REQUIRED kysdk-shortcut)
    pkg_check_modules(KYSDK_NOTIFY REQUIRED kysdk-notification)
    pkg_check_modules(KYSDK_QTWIDGETS REQUIRED kysdk-qtwidgets)
    target_compile_definitions(pixiu-frontend PRIVATE PIXIU_HAVE_KYSDK=1)
    target_include_directories(pixiu-frontend PRIVATE
        ${KYSDK_SHORTCUT_INCLUDE_DIRS}
        ${KYSDK_NOTIFY_INCLUDE_DIRS}
        ${KYSDK_QTWIDGETS_INCLUDE_DIRS}
    )
    target_link_libraries(pixiu-frontend PRIVATE
        ${KYSDK_SHORTCUT_LIBRARIES}
        ${KYSDK_NOTIFY_LIBRARIES}
        ${KYSDK_QTWIDGETS_LIBRARIES}
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
    )
    target_include_directories(t_memory_panel PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_memory_panel PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME memory_panel COMMAND t_memory_panel)

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

    set_tests_properties(websocket_client floating_ball notify_service
        forget_controller forget_dialog memory_panel conflict_controller
        preference_controller shortcut_manager theme_service
        PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endif()
