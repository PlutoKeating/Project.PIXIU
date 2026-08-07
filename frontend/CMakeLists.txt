cmake_minimum_required(VERSION 3.10)

project(pixiu-frontend VERSION 0.1.0 LANGUAGES CXX)

option(PIXIU_HAVE_KYSDK "Build with KylinSDK integration" OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Qt5 5.9 REQUIRED COMPONENTS Widgets)

add_executable(pixiu-frontend
    src/main.cpp
)

target_link_libraries(pixiu-frontend
    PRIVATE
        Qt5::Widgets
)

if(PIXIU_HAVE_KYSDK)
    target_compile_definitions(pixiu-frontend PRIVATE PIXIU_HAVE_KYSDK=1)
endif()
