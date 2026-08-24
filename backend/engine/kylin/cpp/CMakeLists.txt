cmake_minimum_required(VERSION 3.16)
project(kylin_python_bindings LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)
find_package(PkgConfig REQUIRED)

# ── 文本向量化 SDK（kylin-coreai-embedding，C API）───────────────
# 头文件优先用仓库内 submodule；也可改用系统安装路径 /usr/include/kylin-ai
set(KYSDK_EMBEDDING_INCLUDE_DIR
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../../third_party/kylin-coreai-embedding/include"
    CACHE PATH "kylin-coreai-embedding include dir")
find_library(KYSDK_COREAI_EMBEDDING_LIBRARY
             NAMES kysdk-coreai-embedding REQUIRED)
pkg_check_modules(GIO REQUIRED gio-unix-2.0)

pybind11_add_module(_kylin_text_embedding kylin_text_embedding.cpp)
target_include_directories(_kylin_text_embedding
                           PRIVATE ${KYSDK_EMBEDDING_INCLUDE_DIR}
                                   ${GIO_INCLUDE_DIRS})
target_link_libraries(_kylin_text_embedding
                      PRIVATE ${KYSDK_COREAI_EMBEDDING_LIBRARY}
                              ${GIO_LIBRARIES})

# ── 向量数据库 SDK（libkysdk-vector-engine-client，C++ API）──────
set(KYSDK_VECTOR_INCLUDE_DIR
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../../third_party/libkysdk-vector-engine-client/include"
    CACHE PATH "kysdk-vector-engine-client include dir")
find_library(KYSDK_VECTOR_CLIENT_LIBRARY
             NAMES kysdk-vector-engine-client REQUIRED)

pybind11_add_module(_kylin_vector_client kylin_vector_client.cpp)
target_include_directories(_kylin_vector_client
                           PRIVATE ${KYSDK_VECTOR_INCLUDE_DIR})
target_link_libraries(_kylin_vector_client
                      PRIVATE ${KYSDK_VECTOR_CLIENT_LIBRARY})

# ── OCR SDK（libkyocr，C++ API）—— 可选：找到头文件与库才构建 ────
find_library(KYSDK_OCR_LIBRARY NAMES kyocr)
find_path(KYSDK_OCR_INCLUDE_DIR kysdk/kysdk-system/libkyocr.hpp)
set(PIXIU_KYLIN_OPTIONAL_TARGETS "")
if(KYSDK_OCR_LIBRARY AND KYSDK_OCR_INCLUDE_DIR)
    pybind11_add_module(_kylin_ocr kylin_ocr.cpp)
    target_include_directories(_kylin_ocr PRIVATE ${KYSDK_OCR_INCLUDE_DIR})
    target_link_libraries(_kylin_ocr PRIVATE ${KYSDK_OCR_LIBRARY})
    list(APPEND PIXIU_KYLIN_OPTIONAL_TARGETS _kylin_ocr)
    message(STATUS "libkyocr found: building _kylin_ocr")
else()
    message(STATUS "libkyocr not found: skipping _kylin_ocr")
endif()

# 产物输出到 backend/engine/kylin/（与 __init__.py 同级，便于直接 import）
install(TARGETS _kylin_text_embedding _kylin_vector_client
                ${PIXIU_KYLIN_OPTIONAL_TARGETS}
        LIBRARY DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}/..)
