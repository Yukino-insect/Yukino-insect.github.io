+++
date = '2025-12-17T09:46:44+08:00'
draft = false
title = '复原 IP 地址'
+++

```java
class Solution {

    // 整个 ip 分为四段
    static final int SEG_COUNT = 4;
    // 结果
    List<String> res = new ArrayList<>();
    // 四段
    int[] segments = new int[SEG_COUNT];

    public List<String> restoreIpAddresses(String s) {
        segments = new int[SEG_COUNT];
        // 递归调用，第一个参数是字符串的起始位置，第二个参数是筛选第几段ip片段
        dfs(s, 0, 0);
        return res;    
    }

    public void dfs(String s, int segId, int segStart) {
        // 如果找到了四段ip并且遍历完了整个字符串，就是一种答案
        if (segId == SEG_COUNT) {
            if (segStart == s.length()) {
                StringBuffer ipAddr = new StringBuffer();
                for (int i = 0; i < SEG_COUNT; i++) {
                    // 从 segments 中拼接四段 ip
                    ipAddr.append(segments[i]);
                    // 每段 ip 之间需要有 . 分割
                    if (i != SEG_COUNT - 1) {
                        ipAddr.append('.');
                    }
                }
                // 添加答案
                res.add(ipAddr.toString());
            }
            return;
        }
        // 如果 起始位置是字符串末尾，直接返回
        if (segStart == s.length()) {
            return;
        }
        //如果起始位置是 0 特殊处理，保存 0 作为一段 ip 并且开启下一次递归
        if (s.charAt(segStart) == '0') {
            segments[segId] = 0;
            dfs(s, segId + 1, segStart + 1);
            return;
        }
        int addr = 0;
        // 计算某一段的 ip
        for (int segEnd = segStart; segEnd < s.length(); segEnd++) {
            addr = addr * 10 + (s.charAt(segEnd) - '0');
            // addr 要大于 0 小于等于 255
            if (addr > 0 && addr <= 0xFF) {
                // 记住当前符合条件的值
                segments[segId] = addr;
                // 递归下一次
                dfs(s, segId + 1, segEnd + 1);
            } else {
                // 如果 addr 的结果超过 255 直接结束当次循环
                break;
            }
        }
    }
}
```
