#ifndef PIXIU_UKUI_WINDOW_H
#define PIXIU_UKUI_WINDOW_H

class QWidget;

// UKUI 窗口辅助：为无边框顶层窗口应用麒麟原生窗口装饰能力。
//
// 麒麟环境（PIXIU_HAVE_KYSDK）：通过 kysdk-qtwidgets 的 KShadowHelper 给窗口
// 添加 UKUI 风格圆角阴影；浅色/深色主题下均生效，不改变窗口几何与布局。
// 开发态/降级（无 KYSDK）：空操作，保持现有 Qt Widgets 表现，不阻塞调用方。
//
// 使用约定：窗口构造完成后调用 decorateUkuiWindow(this, borderRadius)；
// 适配层内部收敛全部 KYSDK 条件编译，UI 组件中不得散落 #ifdef。
namespace pixiu {

// 当前环境是否具备 UKUI 窗口装饰能力。
bool ukuiWindowAvailable();

// 为无边框顶层窗口应用 UKUI 阴影/圆角装饰；降级环境下为 no-op。
void decorateUkuiWindow(QWidget *window, int borderRadius = 12);

} // namespace pixiu

#endif // PIXIU_UKUI_WINDOW_H
