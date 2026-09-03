// 麒麟 coreai/embedding 文本向量化 —— pybind11 绑定
//
// 封装 SDK 同步 C API（libkysdk-coreai-embedding）：
//   text_embedding_create_session / init_session / get_model_list /
//   init_model / text_embedding / embedding_result_* / destroy_session

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <kylin-ai/coreai/embedding/embedding.h>

#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

namespace {

bool IsTextModelName(const char *name) {
    if (name == nullptr) {
        return false;
    }
    std::string n(name);
    // 文本模型名称形如 "ensemble-embd_gte-base_uint8-text"
    return n.find("-text") != std::string::npos ||
           n.find("text") != std::string::npos;
}

std::string SelectModelName(TextEmbeddingSession *session) {
    int err = 0;
    EmbeddingModelList *list = text_embedding_get_model_list(session, &err);
    if (list == nullptr || err != 0) {
        throw std::runtime_error("text_embedding_get_model_list failed, err=" +
                                 std::to_string(err));
    }
    int count = embedding_model_list_get_count(list, &err);
    if (count <= 0) {
        throw std::runtime_error("麒麟 AI 运行时无可用文本向量化模型");
    }
    for (int i = 0; i < count; ++i) {
        const EmbeddingModelInfo *info =
            embedding_model_list_get_model(list, i, &err);
        if (info == nullptr) {
            continue;
        }
        const char *name = embedding_model_info_get_model_name(info, &err);
        if (IsTextModelName(name)) {
            return std::string(name);
        }
    }
    const EmbeddingModelInfo *first =
        embedding_model_list_get_model(list, 0, &err);
    const char *firstName =
        first ? embedding_model_info_get_model_name(first, &err) : nullptr;
    return firstName ? std::string(firstName) : "";
}

int ModelDim(TextEmbeddingSession *session, const std::string &model_name) {
    int err = 0;
    EmbeddingModelList *list = text_embedding_get_model_list(session, &err);
    if (list == nullptr || err != 0) {
        throw std::runtime_error("text_embedding_get_model_list failed, err=" +
                                 std::to_string(err));
    }
    int count = embedding_model_list_get_count(list, &err);
    for (int i = 0; i < count; ++i) {
        const EmbeddingModelInfo *info =
            embedding_model_list_get_model(list, i, &err);
        if (info == nullptr) {
            continue;
        }
        const char *name = embedding_model_info_get_model_name(info, &err);
        if (name != nullptr && model_name == name) {
            int dim = embedding_model_info_get_model_dim(info, &err);
            if (err != 0 || dim <= 0) {
                throw std::runtime_error("invalid embedding model dimension");
            }
            return dim;
        }
    }
    throw std::runtime_error("selected embedding model missing from model list");
}

}  // namespace

class KylinTextEmbedding {
public:
    explicit KylinTextEmbedding(std::string model_name) {
        session_ = text_embedding_create_session();
        if (session_ == nullptr) {
            throw std::runtime_error("text_embedding_create_session failed");
        }
        try {
            if (text_embedding_init_session(session_) != 0) {
                throw std::runtime_error(
                    "text_embedding_init_session failed：无法连接麒麟 AI 运行时服务");
            }
            if (model_name.empty()) {
                model_name = SelectModelName(session_);
            }
            if (model_name.empty()) {
                throw std::runtime_error("无可用文本向量化模型");
            }
            if (text_embedding_init_model(session_, model_name.c_str()) != 0) {
                throw std::runtime_error("text_embedding_init_model failed: " +
                                         model_name);
            }
            model_name_ = model_name;
            dim_ = ModelDim(session_, model_name);
        } catch (...) {
            text_embedding_destroy_session(&session_);
            throw;
        }
    }

    ~KylinTextEmbedding() {
        if (session_ != nullptr) {
            text_embedding_destroy_session(&session_);
            session_ = nullptr;
        }
    }

    KylinTextEmbedding(const KylinTextEmbedding &) = delete;
    KylinTextEmbedding &operator=(const KylinTextEmbedding &) = delete;

    std::vector<float> embed(const std::string &text) {
        std::lock_guard<std::mutex> lock(mutex_);
        EmbeddingResult *result = nullptr;
        if (session_ == nullptr || !text_embedding(session_, text.c_str(), &result) ||
            result == nullptr) {
            throw std::runtime_error("text_embedding failed");
        }
        int code = embedding_result_get_error_code(result);
        if (code != 0) {
            const char *msg = embedding_result_get_error_message(result);
            std::string message = msg != nullptr ? msg : "unknown";
            embedding_result_destroy(&result);
            throw std::runtime_error("text_embedding error " +
                                     std::to_string(code) + ": " + message);
        }
        float *data = embedding_result_get_vector_data(result);
        int length = embedding_result_get_vector_length(result);
        if (data == nullptr || length != dim_) {
            embedding_result_destroy(&result);
            throw std::runtime_error("text_embedding returned invalid dimension");
        }
        std::vector<float> vec(data, data + length);
        embedding_result_destroy(&result);
        return vec;
    }

    int dim() const { return dim_; }

    std::string model_name() const { return model_name_; }

private:
    TextEmbeddingSession *session_ = nullptr;
    int dim_ = 768;
    std::string model_name_;
    std::mutex mutex_;
};

PYBIND11_MODULE(_kylin_text_embedding, m) {
    m.doc() = "麒麟 coreai/embedding 文本向量化绑定（libkysdk-coreai-embedding）";
    py::class_<KylinTextEmbedding>(m, "KylinTextEmbedding")
        .def(py::init<std::string>(), py::arg("model_name") = std::string())
        .def("embed", &KylinTextEmbedding::embed,
             py::call_guard<py::gil_scoped_release>())
        .def("dim", &KylinTextEmbedding::dim)
        .def("model_name", &KylinTextEmbedding::model_name);
}
