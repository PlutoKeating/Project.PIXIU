#include "app/UkuiWindow.h"

#include <QLoggingCategory>
#include <QWidget>

#ifdef PIXIU_HAVE_KYSDK
#include <kshadowhelper.h>
#endif

Q_LOGGING_CATEGORY(lcUkuiWindow, "pixiu.ukui-window")

namespace pixiu {

bool ukuiWindowAvailable()
{
#ifdef PIXIU_HAVE_KYSDK
    return true;
#else
    return false;
#endif
}

void decorateUkuiWindow(QWidget *window, int borderRadius)
{
#ifdef PIXIU_HAVE_KYSDK
    if (!window) {
        return;
    }
    // UKUI 原生窗口阴影；圆角半径与窗口自绘圆角保持一致，阴影宽度/浓度取默认值。
    kdk::effects::KShadowHelper::self()->setWidget(window, borderRadius);
    qCInfo(lcUkuiWindow) << "UKUI window shadow applied, radius:" << borderRadius;
#else
    Q_UNUSED(window)
    Q_UNUSED(borderRadius)
    qCInfo(lcUkuiWindow) << "UKUI window decoration disabled (fallback mode)";
#endif
}

} // namespace pixiu
