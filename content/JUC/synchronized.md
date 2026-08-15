+++
date = '2025-12-12T19:09:22+08:00'
draft = false
title = 'synchronized'
+++

`synchronized` 是 Java 语法层面提供的一个锁机制，是 Java 并发模型中最经典、最基础的同步机制之一，用于保证代码块或方法的原子性和可见性

`synchronized` 有三种用法

```java 
// 修饰代码块
synchronized (lock) {
    
}

// 修饰方法
public synchronized void method() {
    
}

// 修饰静态方法
public static synchronized void method() {
    
}
```

修饰代码块需要自己显示的提供对象锁 

```java
public class Demo {
    private static Object lockA;
    private static Object lockB;
    
    public void method1() {
        synchronized (lockA) {
            
        }
    }
    
    public void method2() {
        synchronized (lockB) {
            
        }
    }
} 
```

上面的代码中，我们创建了两个锁，分别用于两个同步代码块，多个线程只会竞争对应的锁

使用 `synchronized` 修饰普通方法并没有显示的为其指定锁，但是默认是锁定当前对象，也就是 `this`

使用 `synchronized` 修饰静态方法时默认是锁定当前类，即 `Class`

### synchronized 底层的实现机制

`synchronized` 在编译后，会生成两个关键的 JVM 字节码指令

- `monitorenter` 获取对象的 Monitor
- `monitorexit` 释放对象的 Monitor

当 JVM 执行到 `monitorenter` 时，会尝试去获取为 `synchronized` 指定的对象的 Monitor 锁，执行完同步代码块后，通过 `monitorexit` 释放锁

**Monitor** 是什么呢

这就涉及到了对象在 JVM 中的内存结构

每一个对象在 JVM 中分为三部分

- 对象头
- 对象体
- 填充字节

锁机制就涉及到了对象头，它的组成部分为

- Mark Word：存放锁标志、hashCode、GC标志、线程ID 等
- Kalss Ponter
- 数组长度（可选）

`synchronized` 底层的执行流程

```markdown
Thread -> monitorenter
   ↓
检查对象的 Mark Word
   ↓
  无锁状态？-> 尝试 CAS 竞争
   ↓
  成功？-> 获取锁
   ↓
  失败？-> 自旋等待 or 锁膨胀
   ↓
  获得锁后，执行临界区
   ↓
  monitorexit -> 释放锁
```

从上述的执行流程可知，线程会通过检查对象的 Mark Word 来获取其对应的 Monitor

`synchronized` 的底层机制是基于 **对象头（Mark Word）+ Monitor 结构** 的对象级锁实现。
 它通过 **monitorenter / monitorexit** 指令操作对象的 **Monitor**，
 并通过 **偏向锁 -> 轻量级锁 -> 重量级锁** 的升级策略，在性能与安全之间取得平衡

## Monitor 是什么？

Monitor（监视器锁）是 **JVM 层实现对象锁的结构**，底层对应 **操作系统的 Mutex（互斥量）**。

每个对象在 JVM 中都有一个 **ObjectMonitor**（C++实现），
 当锁升级为重量级锁时，线程的锁竞争就交由这个 Monitor 来管理。

Monitor 内部有：

| 字段           | 含义                             |
| -------------- | -------------------------------- |
| **Owner**      | 当前持有锁的线程                 |
| **EntryList**  | 等待获取锁的线程队列（阻塞）     |
| **WaitSet**    | 调用 `wait()` 进入等待的线程集合 |
| **Recursions** | 重入计数                         |
| **Condition**  | 用于实现 `wait()/notify()`       |

------

##  三、锁是如何升级到 Monitor（重量级锁）的

1. **初始状态（无锁 / 偏向锁）**

- 没有竞争或仅单线程访问；
- JVM 在对象头的 Mark Word 中存储锁标志和线程ID。

2. **轻量级锁阶段**

- 第二个线程尝试获取锁；
- 通过 **CAS（Compare-And-Swap）** 尝试加锁；
- 如果能自旋等待（短暂竞争），仍保持轻量级锁。

3. **锁竞争严重（CAS多次失败）**

- JVM 认为竞争过于频繁；
- 会将锁升级为 **重量级锁（Monitor 锁）**；
- 线程进入 **阻塞状态（Block）**；
- Monitor 使用操作系统的 **互斥锁（mutex）+ 条件变量** 控制调度。

------

##  四、Monitor 为什么叫“重量级锁”

因为一旦升级为 Monitor：

| 特征                          | 说明                          |
| ----------------------------- | ----------------------------- |
| 需要系统调用（进入内核态）    | 涉及 OS 的线程挂起与唤醒      |
| 线程阻塞 / 唤醒开销大         | 包含上下文切换                |
| 不再自旋等待                  | 线程进入等待队列（EntryList） |
| 实现依赖 ObjectMonitor（C++） | JVM 的重量级数据结构          |

换句话说：

> 轻量级锁的竞争发生在 **用户态（CAS、自旋）**，
>  而 Monitor 锁的竞争发生在 **内核态（mutex、wait）**。

切换到内核态 = 性能损耗大 -> 因此称为 **重量级锁**。

------

##  五、直观对比：轻量级锁 vs 重量级锁

| 对比项   | 轻量级锁（CAS + 自旋） | 重量级锁（Monitor） |
| -------- | ---------------------- | ------------------- |
| 加锁方式 | CAS 尝试修改 Mark Word | 使用操作系统 Mutex  |
| 阻塞机制 | 不阻塞（自旋等待）     | 阻塞线程，等待唤醒  |
| 开销     | 低                     | 高（内核态切换）    |
| 实现位置 | JVM 用户态             | JVM + OS 内核态     |
| 适合场景 | 短期竞争               | 长时间竞争          |
| 实现结构 | Lock Record            | ObjectMonitor       |

------

##  六、从源码层面看（HotSpot）

在 HotSpot 中，ObjectMonitor（C++定义）是 Monitor 锁的核心：

```
class ObjectMonitor {
  void* Owner;          // 当前持锁线程
  ObjectWaiter* EntryList; // 进入锁等待的线程队列
  ObjectWaiter* WaitSet;   // wait() 等待线程集合
  int Recursions;       // 重入次数
  ...
};
```

当锁升级为重量级锁时：

- 对象头（Mark Word）会被修改为 `monitor` 指针；
- Monitor 负责后续所有的线程阻塞与唤醒逻辑。

------

##  七、可视化流程（简图）

```
Thread A            Thread B            JVM Object
---------            ---------           ------------------
 monitorenter                              [Mark Word]
     │                                           │
     │ 成功获取锁                                │
     │──────────────────────────────────────────- Owner = A
     │                                           │
     │ Thread B 也想获取锁 -> CAS 失败            │
     │──────────────────────────────────────────- 进入 EntryList
     │                                           │
     │ Thread A 执行完释放锁                     │
     │──────────────────────────────────────────- 唤醒 EntryList
     │                                           │
```

此时，Monitor 控制锁的拥有与线程调度。

------

##  八、结论总结

| 结论                                                     | 说明                                               |
| -------------------------------------------------------- | -------------------------------------------------- |
| **Monitor 锁就是重量级锁**                               | 它是 `synchronized` 的底层实现，当锁竞争激烈时触发 |
| **轻量级锁在用户态自旋，不用 Monitor**                   | 用 CAS 机制完成加锁                                |
| **锁升级路径：偏向 -> 轻量级 -> 重量级（Monitor）**        | JVM 动态调整锁的粒度与性能                         |
| **重量级锁的本质：OS Mutex + Condition + ObjectMonitor** | 涉及线程阻塞、唤醒、上下文切换                     |

------

 **一句话记忆：**

>  `Monitor` 是 `synchronized` 最终的“重量级锁”实现，
>  当 CAS 自旋失败后，线程进入阻塞，由 `ObjectMonitor` 管理互斥与等待队列。

------


synchronized 做了一系列升级，在竞争条件尚不激烈的情况下，是不会进行获取操作系统底层提供的监视器锁的，而是先操作对象头
