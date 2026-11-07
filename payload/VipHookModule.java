package com.crack.qimao;

import android.content.Context;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XC_MethodReplacement;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/**
 * 七猫免费小说 (com.kmxs.reader) VIP 修改模块
 *
 * 打包方式二选一:
 *   1) LSPatch 打进 APK (免 Root, 推荐)
 *   2) 装 LSPosed, 作用域勾选 com.kmxs.reader
 *
 * 生效位置:
 *   会员状态   UserVipInfoResponse.isVipStatus()  -> true
 *              UserVipInfoResponse.getStatus()    -> "1"
 *   VIP 时长   UserVipInfoResponse.getVipExpiration() -> 2099-12-31 23:59:59
 *   落库字段   decodeVipResponse() 之后直接改 status / vet 字段
 *   本地缓存   Lol6.Y(Context) 读 USER_IS_VIP -> "1"
 */
public class VipHookModule implements IXposedHookLoadPackage {

    /** 会员状态标记, 服务器约定 "1" = 会员 */
    private static final String VIP_STATUS = "1";
    /** 到期时间 (vet 字段, 日期串格式) */
    private static final String VIP_EXPIRE = "2099-12-31 23:59:59";

    private static final String CLS_RESP  = "com.qimao.qmuser.model.response.UserVipInfoResponse";
    private static final String CLS_MODEL = "com.qimao.qmuser.model.UserVipModel";
    /** 本地缓存混淆类 (classes3.dex), 版本变了可能改名, 失败会自动跳过 */
    private static final String CLS_CACHE = "ol6";

    @Override
    public void handleLoadPackage(final XC_LoadPackage.LoadPackageParam lpparam) throws Throwable {
        if (!"com.kmxs.reader".equals(lpparam.packageName)) {
            return;
        }
        XposedBridge.log("[VipHook] package matched: " + lpparam.packageName);

        hookResponse(lpparam);
        hookModel(lpparam);
        hookCache(lpparam);
    }

    /** 1. 响应实体: 直接改返回值 */
    private void hookResponse(XC_LoadPackage.LoadPackageParam lpparam) {
        try {
            Class<?> resp = XposedHelpers.findClass(CLS_RESP, lpparam.classLoader);

            XposedHelpers.findAndHookMethod(resp, "isVipStatus",
                    XC_MethodReplacement.returnConstant(true));

            XposedHelpers.findAndHookMethod(resp, "getStatus",
                    XC_MethodReplacement.returnConstant(VIP_STATUS));

            // getVipExpiration 改返回值的同时把字段写掉, 防止别处直接读 vet
            XposedHelpers.findAndHookMethod(resp, "getVipExpiration", new XC_MethodHook() {
                @Override
                protected void beforeHookedMethod(MethodHookParam param) throws Throwable {
                    try {
                        XposedHelpers.setObjectField(param.thisObject, "vet", VIP_EXPIRE);
                    } catch (Throwable ignored) {
                    }
                }

                @Override
                protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                    param.setResult(VIP_EXPIRE);
                }
            });

            XposedBridge.log("[VipHook] response entity hooked");
        } catch (Throwable t) {
            XposedBridge.log("[VipHook] response hook failed: " + t);
        }
    }

    /** 2. 解码出口: 服务器数据解密后立刻改字段 (最彻底) */
    private void hookModel(XC_LoadPackage.LoadPackageParam lpparam) {
        try {
            Class<?> model = XposedHelpers.findClass(CLS_MODEL, lpparam.classLoader);
            Class<?> resp = XposedHelpers.findClass(CLS_RESP, lpparam.classLoader);

            // decodeVipResponse(UserVipResponse) -> UserVipInfoResponse
            XposedHelpers.findAndHookMethod(model, "decodeVipResponse",
                    XposedHelpers.findClass("com.qimao.qmuser.model.response.UserVipResponse",
                            lpparam.classLoader),
                    new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                            Object info = param.getResult();
                            if (info == null) {
                                return;
                            }
                            try {
                                XposedHelpers.setObjectField(info, "status", VIP_STATUS);
                                XposedHelpers.setObjectField(info, "vet", VIP_EXPIRE);
                                XposedBridge.log("[VipHook] decodeVipResponse -> patched");
                            } catch (Throwable t) {
                                XposedBridge.log("[VipHook] patch failed: " + t);
                            }
                        }
                    });

            // saveVipInfo(UserVipInfoResponse) 兜一层
            XposedHelpers.findAndHookMethod(model, "saveVipInfo", resp, new XC_MethodHook() {
                @Override
                protected void beforeHookedMethod(MethodHookParam param) throws Throwable {
                    Object info = param.args[0];
                    if (info == null) {
                        return;
                    }
                    try {
                        XposedHelpers.setObjectField(info, "status", VIP_STATUS);
                        XposedHelpers.setObjectField(info, "vet", VIP_EXPIRE);
                    } catch (Throwable ignored) {
                    }
                }
            });

            XposedBridge.log("[VipHook] model hooked");
        } catch (Throwable t) {
            XposedBridge.log("[VipHook] model hook failed: " + t);
        }
    }

    /** 3. 本地缓存: Lol6.Y(Context) 读 USER_IS_VIP, 默认 "0" */
    private void hookCache(XC_LoadPackage.LoadPackageParam lpparam) {
        try {
            Class<?> cache = XposedHelpers.findClass(CLS_CACHE, lpparam.classLoader);
            XposedHelpers.findAndHookMethod(cache, "Y", Context.class, new XC_MethodHook() {
                @Override
                protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                    Object v = param.getResult();
                    if (v == null || "0".equals(v) || "".equals(v)) {
                        param.setResult(VIP_STATUS);
                    }
                }
            });
            XposedBridge.log("[VipHook] cache hooked");
        } catch (Throwable t) {
            // 混淆类名可能随版本变化, 失败不影响主流程
            XposedBridge.log("[VipHook] cache hook skipped: " + t);
        }
    }
}
