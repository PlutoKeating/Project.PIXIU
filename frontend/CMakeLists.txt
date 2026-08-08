cmake_minimum_required(VERSION 3.10)

project(pixiu-frontend VERSION 0.1.0 LANGUAGES CXX)

option(PIXIU_HAVE_KYSDK "Build with KylinSDK integration" OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

find_package(Qt5 5.9 REQUIRED COMPONENTS Widgets Network)

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
    src/widgets/FloatingBall.h
    src/widgets/FloatingBall.cpp
    src/widgets/ChatWindow.h
    src/widgets/ChatWindow.cpp
    src/widgets/InputBar.h
    src/widgets/InputBar.cpp
    src/widgets/MessageList.h
    src/widgets/MessageList.cpp
    src/models/ChatMessage.h
    src/services/BackendTypes.h
    src/services/BackendTransport.h
    src/services/BackendTransport.cpp
    src/services/HttpBackendTransport.h
    src/services/HttpBackendTransport.cpp
)

target_link_libraries(pixiu-frontend
    PRIVATE
        Qt5::Widgets
        Qt5::Network
)

target_include_directories(pixiu-frontend
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(PIXIU_HAVE_KYSDK)
    target_compile_definitions(pixiu-frontend PRIVATE PIXIU_HAVE_KYSDK=1)
endif()
