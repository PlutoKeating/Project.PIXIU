// 麒麟向量数据库客户端（libkysdk-vector-engine-client）—— pybind11 绑定
//
// 封装 C++ API（Milvus 式）：Database::Create / Connect / HasCollection /
// CreateCollection / DropCollection / Insert / Search。

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <kysdk-vector-engine-client/Database.h>

#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;
using namespace VectorDB;

namespace {

[[noreturn]] void ThrowStatus(const std::string &prefix, const Status &st) {
    throw std::runtime_error(
        prefix + " failed: code=" +
        std::to_string(static_cast<int>(st.Code())) + " msg=" + st.Message());
}

}  // namespace

class VectorEngineClient {
public:
    VectorEngineClient(const std::string &app_id, const std::string &host,
                       uint16_t port) {
        client_ = Database::Create();
        if (!client_) {
            throw std::runtime_error("VectorDB::Database::Create failed");
        }
        Status st = client_->Connect(ConnectParam(app_id, host, port));
        if (!st.IsOk()) {
            ThrowStatus("Connect", st);
        }
    }

    bool HasCollection(const std::string &name) {
        bool has = false;
        Status st = client_->HasCollection(name, has);
        if (!st.IsOk()) {
            ThrowStatus("HasCollection", st);
        }
        return has;
    }

    void CreateCollection(const std::string &name, int dim, bool auto_id,
                          bool dynamic) {
        Status st = client_->CreateCollection(name, dim, auto_id, dynamic);
        if (!st.IsOk()) {
            ThrowStatus("CreateCollection", st);
        }
    }

    void DropCollection(const std::string &name) {
        Status st = client_->DropCollection(name);
        if (!st.IsOk()) {
            ThrowStatus("DropCollection", st);
        }
    }

    int Insert(const std::string &name,
               const std::vector<std::vector<float>> &vectors,
               const std::vector<int64_t> &ids) {
        std::vector<FieldDataPtr> fields;
        fields.push_back(std::make_shared<FloatVecFieldData>(
            DEFAULT_VECTOR_FIELD_NAME, vectors));
        if (!ids.empty()) {
            fields.insert(fields.begin(),
                          std::make_shared<Int64FieldData>(DEFAULT_ID_FIELD_NAME,
                                                           ids));
        }
        DmlResults results;
        Status st = client_->Insert(name, fields, results);
        if (!st.IsOk()) {
            ThrowStatus("Insert", st);
        }
        return static_cast<int>(results.IdArray().IntIDArray().size());
    }

    py::list Search(const std::string &name, const std::vector<float> &query,
                    int top_k) {
        SearchArguments args(name, top_k);
        args.AddOutputField(DEFAULT_ID_FIELD_NAME);
        Status st = args.AddTargetVector(DEFAULT_VECTOR_FIELD_NAME, query);
        if (!st.IsOk()) {
            ThrowStatus("AddTargetVector", st);
        }

        SearchResults results;
        st = client_->Search(args, results);
        if (!st.IsOk()) {
            ThrowStatus("Search", st);
        }

        py::list out;
        for (const SingleResult &single : results.Results()) {
            const IDArray &ids = single.Ids();
            const std::vector<float> &scores = single.Scores();
            if (ids.IsIntegerID()) {
                const std::vector<int64_t> &id_vec = ids.IntIDArray();
                for (size_t i = 0; i < id_vec.size(); ++i) {
                    py::dict row;
                    row["id"] = id_vec[i];
                    row["score"] = i < scores.size() ? scores[i] : 0.0f;
                    out.append(row);
                }
            } else {
                const std::vector<std::string> &id_vec = ids.StrIDArray();
                for (size_t i = 0; i < id_vec.size(); ++i) {
                    py::dict row;
                    row["id"] = id_vec[i];
                    row["score"] = i < scores.size() ? scores[i] : 0.0f;
                    out.append(row);
                }
            }
        }
        return out;
    }

private:
    std::shared_ptr<Database> client_;
};

PYBIND11_MODULE(_kylin_vector_client, m) {
    m.doc() = "麒麟向量数据库客户端绑定（libkysdk-vector-engine-client）";
    py::class_<VectorEngineClient>(m, "VectorEngineClient")
        .def(py::init<const std::string &, const std::string &, uint16_t>())
        .def("has_collection", &VectorEngineClient::HasCollection)
        .def("create_collection", &VectorEngineClient::CreateCollection)
        .def("drop_collection", &VectorEngineClient::DropCollection)
        .def("insert", &VectorEngineClient::Insert)
        .def("search", &VectorEngineClient::Search);
}
