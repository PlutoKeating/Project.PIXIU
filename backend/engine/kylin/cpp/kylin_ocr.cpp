// 麒麟 kysdk-ocr 文字识别 —— pybind11 绑定
//
// 封装 kdk::kdkOCR（libkyocr）：
//   getCls(imagePath, nums) -> 识别出的文字行列表

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <kysdk/kysdk-system/libkyocr.hpp>

#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

class KylinOcr {
public:
    // nums：PaddleOCR 并行识别栈个数，默认 4（SDK 文档建议值）。
    std::vector<std::string> recognize(const std::string &image_path, int nums) {
        try {
            kdk::kdkOCR ocr;
            return ocr.getCls(image_path, nums);
        } catch (const std::exception &exc) {
            throw std::runtime_error(std::string("kysdk-ocr 识别失败: ") + exc.what());
        }
    }
};

PYBIND11_MODULE(_kylin_ocr, m) {
    m.doc() = "麒麟 kysdk-ocr 文字识别绑定（libkyocr）";
    py::class_<KylinOcr>(m, "KylinOcr")
        .def(py::init<>())
        .def("recognize", &KylinOcr::recognize, py::arg("image_path"),
             py::arg("nums") = 4);
}
