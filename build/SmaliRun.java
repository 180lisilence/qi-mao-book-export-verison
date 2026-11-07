import java.lang.reflect.Method;

public class SmaliRun {
    public static void main(String[] args) throws Exception {
        String cls = args[0];
        String[] rest = new String[args.length - 1];
        System.arraycopy(args, 1, rest, 0, rest.length);
        Class<?> c = Class.forName(cls);
        Method found = null;
        for (Method m : c.getDeclaredMethods()) {
            if (m.getName().equals("main") && m.getParameterCount() == 1
                    && m.getParameterTypes()[0] == String[].class) {
                found = m;
                break;
            }
        }
        if (found == null) {
            System.out.println("候选 main 方法列表:");
            for (Method m : c.getDeclaredMethods()) {
                if (m.getName().equals("main")) System.out.println("  " + m);
            }
            return;
        }
        found.setAccessible(true);
        found.invoke(null, (Object) rest);
    }
}
