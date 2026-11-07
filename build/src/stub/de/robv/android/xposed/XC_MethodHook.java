/*
 * 编译期 stub —— 运行时会被 classes17.dex 里的真实实现覆盖。
 * 不要放在最终 dex 里。
 */
package de.robv.android.xposed;

public abstract class XC_MethodHook {

    public static class MethodHookParam {
        public Object thisObject;
        public Object[] args;

        public Object getResult() {
            return null;
        }
    }

    public static class Unhook {
    }

    protected void beforeHookedMethod(MethodHookParam param) throws Throwable {
    }

    protected void afterHookedMethod(MethodHookParam param) throws Throwable {
    }
}
