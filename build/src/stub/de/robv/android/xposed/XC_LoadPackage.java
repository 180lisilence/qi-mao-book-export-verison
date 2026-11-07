/*
 * 编译期 stub —— 运行时会被 classes17.dex 里的真实实现覆盖。
 * 不要放在最终 dex 里。
 */
package de.robv.android.xposed;

public abstract class XC_LoadPackage {

    public static class LoadPackageParam {
        public String packageName;
        public String processName;
        public ClassLoader classLoader;
        public boolean isFirstApplication;
    }
}
