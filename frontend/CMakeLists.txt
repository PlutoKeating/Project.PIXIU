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
    target_compile_definitions(pixiu-frontend PRIVATE PIXIU_HAVE_KYSDK=1)
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

    set_tests_properties(websocket_client floating_ball
        PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endif()
