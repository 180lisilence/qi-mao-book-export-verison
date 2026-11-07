/*
 * 编译期 stub —— 运行时会被 classes17.dex 里的真实实现覆盖。
 * 不要放在最终 dex 里。
 */
package de.robv.android.xposed;

import java.lang.reflect.Member;

public class XposedHelpers {

    public static Class<?> findClass(String className, ClassLoader classLoader) {
        throw new UnsupportedOperationException("stub");
    }

    public static XC_MethodHook.Unhook findAndHookMethod(Class<?> clazz,
                                                        String methodName,
                                                        Object... parameterTypesAndCallback) {
        throw new UnsupportedOperationException("stub");
    }

    public static XC_MethodHook.Unhook findAndHookMethod(String className,
                                                        ClassLoader classLoader,
                                                        String methodName,
                                                        Object... parameterTypesAndCallback) {
        throw new UnsupportedOperationException("stub");
    }

    public static Member findMethodExact(Class<?> clazz, String methodName, Object... parameterTypes) {
        throw new UnsupportedOperationException("stub");
    }
}
