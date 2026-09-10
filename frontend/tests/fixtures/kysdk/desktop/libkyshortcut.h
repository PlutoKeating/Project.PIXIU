#pragma once
// Test-only ABI fixture; never copied to product exports or SDK evidence.
#define KYSDK_SUCCESS 0
#define KYSDK_SHORTCUT_NAME_ERROR -1
#define KYSDK_SHORTCUT_NOT_EXISTS -4
#define KYSDK_SHORTCUT_EXISTED -5
struct KYSDKGlobalShortcutInfo {
    char *compenteName;
    char *name;
    unsigned int keys[4];
    char *action;
};
struct KYSDKGlobalShortcutInfoList {
    KYSDKGlobalShortcutInfo *data;
    KYSDKGlobalShortcutInfoList *next;
};
KYSDKGlobalShortcutInfoList *kdk_shortcut_get_global_shortcuts_by_key(const char *);
void kdk_shortcut_destroy_info_list(KYSDKGlobalShortcutInfoList *);
int kdk_shortcut_create_global_shortcut(const char *, const char *, const char *);
int kdk_shortcut_set_global_shortcut(const char *, const char *, const char *);
int kdk_shortcut_delete_global_shortcut(const char *);
