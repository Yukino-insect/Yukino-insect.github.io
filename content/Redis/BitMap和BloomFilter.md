+++
date = '2025-12-14T18:11:52+08:00'
draft = false
title = 'Redis Bitmap 和 Bloom Filter'
+++

Bitmap 和 Bloom Filter 都适合处理“是否存在”这类问题，但它们解决的不是同一种场景。

Bitmap 是精确的位图，适合用整数 offset 表示二值状态。Bloom Filter 是概率型数据结构，适合用较小空间判断一个元素是否可能存在，代价是存在误判。

## 一、Bitmap 是什么

Redis 的 Bitmap 不是独立数据类型，而是基于 String 的位操作。Redis String 本质上是二进制安全的字节序列，因此可以把每一位当成一个状态位来使用。

常用命令：

```bash
SETBIT user:1001:signin:2025 0 1
SETBIT user:1001:signin:2025 1 1
GETBIT user:1001:signin:2025 1
BITCOUNT user:1001:signin:2025
```

`SETBIT key offset value` 中的 offset 是从 0 开始的位偏移量。`BITCOUNT` 默认统计值为 1 的 bit 数量。

例如用 Bitmap 记录用户一年签到：

```bash
# 第 1 天签到
SETBIT signin:2025:user:1001 0 1

# 第 32 天签到
SETBIT signin:2025:user:1001 31 1

# 统计全年签到天数
BITCOUNT signin:2025:user:1001
```

一年 365 天只需要 365 bit，约 46 字节。对于大量二值状态来说，这种空间效率非常高。

## 二、Bitmap 的位运算

Bitmap 支持多个 key 之间做位运算：

```bash
BITOP AND active:both active:2025-09-01 active:2025-09-02
BITOP OR active:any active:2025-09-01 active:2025-09-02
BITOP XOR active:diff active:2025-09-01 active:2025-09-02
BITOP NOT active:not active:2025-09-01
```

常见用途：

1. 统计连续多天活跃用户。
2. 统计任意一天活跃用户。
3. 对比两天状态差异。
4. 做大量布尔标记的批量计算。

## 三、Bitmap 的适用条件

Bitmap 的优势成立有一个重要前提：offset 范围可控，并且数据不要过于稀疏。

适合：

1. 用户 ID 连续或经过压缩映射。
2. 状态只有 0 和 1。
3. 只需要判断是否存在或统计数量。
4. 不需要直接取出完整成员列表。

不适合：

1. 用户 ID 非常稀疏，例如最大 ID 已经到几十亿，但实际只有少量用户。
2. 状态不止两种。
3. 需要频繁列出所有命中的成员。
4. 需要存储复杂对象。

如果只设置 offset 为 `20`、`30` 和 `88888888` 的三个位置，Redis 仍然需要为最大 offset 附近分配空间。此时 Bitmap 可能比 Set 更浪费。

对于稀疏整数集合，可以了解 Roaring Bitmap。它是一种可压缩位图结构，适合表示大量整数集合并做高效集合运算。不过 Redis 原生命令并不直接等价提供 Roaring Bitmap 的完整能力，通常需要客户端库或专门模块支持。

## 四、Java 中的简单位图

Java 标准库提供了 `BitSet`，可以直接实现类似能力：

```java
import java.util.BitSet;

public class BitmapDemo {
    public static void main(String[] args) {
        BitSet bitmap = new BitSet(1000);

        bitmap.set(10);
        bitmap.set(200);

        System.out.println(bitmap.get(10));  // true
        System.out.println(bitmap.get(200)); // true
        System.out.println(bitmap.get(300)); // false
        System.out.println(bitmap.cardinality()); // 2
    }
}
```

如果自己用 `byte[]` 实现，也可以更直观地理解位运算：

```java
public class SimpleBitmap {
    private final byte[] bits;

    public SimpleBitmap(int size) {
        this.bits = new byte[size / 8 + 1];
    }

    public void add(int value) {
        int byteIndex = value / 8;
        int bitIndex = value % 8;
        bits[byteIndex] |= (1 << bitIndex);
    }

    public boolean contains(int value) {
        int byteIndex = value / 8;
        int bitIndex = value % 8;
        return (bits[byteIndex] & (1 << bitIndex)) != 0;
    }
}
```

## 五、Bloom Filter 是什么

Bloom Filter，中文常译为布隆过滤器，是一种空间效率很高的概率型数据结构。它用于判断一个元素是否在集合中。

它的判断结果有两个特点：

1. 返回“不存在”时，一定不存在。
2. 返回“存在”时，只能说明可能存在，因为有误判概率。

Bloom Filter 的基本过程是：

1. 准备一个很长的 bit 数组。
2. 使用多个哈希函数计算元素的位置。
3. 添加元素时，把这些位置都置为 1。
4. 查询元素时，重新计算这些位置。
5. 如果任意一个位置是 0，元素一定不存在；如果全部都是 1，元素可能存在。

误判来自哈希碰撞。多个不同元素可能把相同位置置为 1，导致一个从未加入过的元素也被判断为“可能存在”。

## 六、Redis 中使用 Bloom Filter

Redis Open Source 的核心数据结构不直接提供 Bloom Filter 命令。通常使用 Redis Stack 中的 RedisBloom 模块。

常用命令：

```bash
BF.RESERVE bf:product 0.001 1000000
BF.ADD bf:product product:1001
BF.EXISTS bf:product product:1001

BF.MADD bf:product product:1002 product:1003
BF.MEXISTS bf:product product:1002 product:9999
BF.INFO bf:product
```

含义：

1. `BF.RESERVE`：创建过滤器，指定误判率和容量。
2. `BF.ADD` / `BF.MADD`：添加一个或多个元素。
3. `BF.EXISTS` / `BF.MEXISTS`：判断一个或多个元素是否可能存在。
4. `BF.INFO`：查看过滤器信息。

布隆过滤器一般不能像 Set 一样安全地直接删除元素，因为某些 bit 可能被多个元素共享。需要删除能力时，可以考虑 Counting Bloom Filter 或其他结构，但复杂度和空间成本也会增加。

## 七、Bloom Filter 的应用场景

### 1. 缓存穿透防护

查询商品详情前，先判断商品 ID 是否可能存在：

```text
请求 product:1001
  -> Bloom Filter 判断不存在：直接返回空
  -> Bloom Filter 判断可能存在：继续查缓存或数据库
```

这可以挡住大量查询不存在数据的请求，减少数据库压力。

### 2. URL 去重

爬虫抓取网页时，可以把已抓取 URL 放入布隆过滤器。新 URL 到来时先判断是否可能抓取过，从而减少重复抓取。

### 3. 黑名单初筛

例如邮箱、IP、设备指纹等黑名单场景，可以先用布隆过滤器做快速初筛。由于存在误判，命中后通常还要再查一次精确存储。

## 八、Bitmap 与 Bloom Filter 的区别

| 维度 | Bitmap | Bloom Filter |
| --- | --- | --- |
| 是否精确 | 精确 | 有误判 |
| 判断不存在 | 精确 | 精确 |
| 判断存在 | 精确 | 可能存在 |
| 输入类型 | 整数 offset | 任意可哈希元素 |
| 删除元素 | 可以把 bit 置 0，但要看业务语义 | 通常不支持安全删除 |
| 空间效率 | 取决于最大 offset 和稀疏程度 | 通常很高 |
| 典型场景 | 签到、活跃、二值状态 | 缓存穿透、去重、黑名单初筛 |

选择原则很简单：

1. 如果数据天然能映射成紧凑整数 offset，并且要求精确，优先 Bitmap。
2. 如果数据是字符串、URL、商品 ID 等任意元素，并且可以接受误判，优先 Bloom Filter。
3. 如果不能接受误判，又需要完整成员集合，使用 Set 或数据库索引。

## 九、一个简易 Bloom Filter 示例

下面代码只用于理解原理，生产环境不要直接使用这种简单哈希方式：

```java
import java.util.BitSet;

public class SimpleBloomFilter {
    private final BitSet bitSet;
    private final int size;
    private final int hashCount;

    public SimpleBloomFilter(int size, int hashCount) {
        this.size = size;
        this.hashCount = hashCount;
        this.bitSet = new BitSet(size);
    }

    public void add(String value) {
        for (int i = 0; i < hashCount; i++) {
            bitSet.set(hash(value, i));
        }
    }

    public boolean mightContain(String value) {
        for (int i = 0; i < hashCount; i++) {
            if (!bitSet.get(hash(value, i))) {
                return false;
            }
        }
        return true;
    }

    private int hash(String value, int seed) {
        int h = value.hashCode() ^ (seed * 0x9e3779b9);
        return (h & Integer.MAX_VALUE) % size;
    }
}
```

总结一下：Bitmap 追求精确，但要求 offset 模型合适；Bloom Filter 牺牲少量准确性，换取非常低的空间占用。把它们混为一谈，就像把尺子和筛子当成同一种工具，结果自然不会优雅。

## 参考资料

- Redis Bitmap 官方文档：<https://redis.io/docs/latest/develop/data-types/bitmaps/>
- Redis Bloom Filter 官方文档：<https://redis.io/docs/latest/develop/data-types/probabilistic/bloom-filter/>
