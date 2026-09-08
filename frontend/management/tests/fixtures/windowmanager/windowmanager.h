#pragma once
#include <QObject>
#include <QMap>
#include <QVariant>

namespace kdk {
using WindowId = QVariant;
struct WindowInfo {
    bool valid = true;
    bool above = false;
    bool isValid() const { return valid; }
    bool isKeepAbove() const { return above; }
};
class WindowManager : public QObject {
    Q_OBJECT
public:
    struct Entry { quint32 pid; QString title; WindowInfo info; };
    inline static QMap<QString, Entry> entries;
    inline static int requests = 0;
    inline static WindowId requestedId;
    static WindowManager *self() { static WindowManager manager; return &manager; }
    static QList<WindowId> windows() {
        QList<WindowId> ids;
        for (auto i = entries.cbegin(); i != entries.cend(); ++i) ids.append(i.key());
        return ids;
    }
    static quint32 getPid(const WindowId &id) { return entries.value(id.toString()).pid; }
    static QString getWindowTitle(const WindowId &id) { return entries.value(id.toString()).title; }
    static WindowInfo getwindowInfo(const WindowId &id) { return entries.value(id.toString()).info; }
    static void keepWindowAbove(const WindowId &id) { ++requests; requestedId = id; }
signals:
    void windowAdded(const WindowId &id);
    void windowRemoved(const WindowId &id);
    void windowChanged(const WindowId &id);
    void keepAboveChanged(const WindowId &id);
    void titleChanged(const WindowId &id);
};
}
