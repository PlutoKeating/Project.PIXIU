// 麒麟向量数据库客户端（libkysdk-vector-engine-client）—— pybind11 绑定
//
// 封装 C++ API（Milvus 式）：Database::Create / Connect / HasCollection /
// CreateCollection / DropCollection / LoadCollection / Insert / Upsert /
// Delete / Search。

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
    explicit VectorEngineClient(const std::string &app_id) {
        Connect(ConnectParam(app_id));
    }

    VectorEngineClient(const std::string &app_id, const std::string &host,
                       uint16_t port) {
        Connect(ConnectParam(app_id, host, port));
    }

private:
    void Connect(const ConnectParam &params) {
        client_ = Database::Create();
        if (!client_) {
            throw std::runtime_error("VectorDB::Database::Create failed");
        }
        Status st = client_->Connect(params);
        if (!st.IsOk()) {
            ThrowStatus("Connect", st);
        }
    }

public:

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

    void LoadCollection(const std::string &name) {
        Status st = client_->LoadCollection(name);
        if (!st.IsOk()) {
            ThrowStatus("LoadCollection", st);
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

    int Upsert(const std::string &name,
               const std::vector<std::vector<float>> &vectors,
               const std::vector<int64_t> &ids) {
        std::vector<FieldDataPtr> fields{
            std::make_shared<Int64FieldData>(DEFAULT_ID_FIELD_NAME, ids),
            std::make_shared<FloatVecFieldData>(DEFAULT_VECTOR_FIELD_NAME,
                                                vectors),
        };
        DmlResults results;
        Status st = client_->Upsert(name, fields, results);
        if (!st.IsOk()) {
            ThrowStatus("Upsert", st);
        }
        return static_cast<int>(results.IdArray().IntIDArray().size());
    }

    int Delete(const std::string &name, const std::vector<int64_t> &ids) {
        if (ids.empty()) {
            return 0;
        }
        std::string expression = DEFAULT_ID_FIELD_NAME + std::string(" in [");
        for (size_t i = 0; i < ids.size(); ++i) {
            if (i > 0) {
                expression += ",";
            }
            expression += std::to_string(ids[i]);
        }
        expression += "]";

        DmlResults results;
        Status st = client_->Delete(name, expression, results);
        if (!st.IsOk()) {
            ThrowStatus("Delete", st);
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
        .def(py::init<const std::string &>())
        .def(py::init<const std::string &, const std::string &, uint16_t>())
        .def("has_collection", &VectorEngineClient::HasCollection)
        .def("create_collection", &VectorEngineClient::CreateCollection)
        .def("drop_collection", &VectorEngineClient::DropCollection)
        .def("load_collection", &VectorEngineClient::LoadCollection)
        .def("insert", &VectorEngineClient::Insert)
        .def("upsert", &VectorEngineClient::Upsert)
        .def("delete", &VectorEngineClient::Delete)
        .def("search", &VectorEngineClient::Search);
}
