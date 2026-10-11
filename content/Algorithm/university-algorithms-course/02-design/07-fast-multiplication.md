+++
date = '2026-10-09T20:09:00+08:00'
draft = false
title = '分治法的乘法加速：大整数乘法与 Strassen 矩阵乘法'
math = true
+++
分治并不保证比朴素算法快。把问题切成更多小块会缩小单个子问题，却也会增加递归调用；真正能改善渐近复杂度的关键，是通过代数变形**减少昂贵操作的次数**。大整数乘法和 Strassen 矩阵乘法正好展示了这件事。

它们的共同套路是：先按高低位或矩阵块拆分输入，朴素展开本会产生四次或八次子乘法；再把若干交叉项合并重用，从而少做一次子乘法。加减法会变多，但若乘法才是主导代价，收益足以改变指数。

## 一、大整数乘法：四次递归乘法如何减为三次

设十进制整数按 $m$ 位低半部分拆开，$B=10^m$：

$$
x=aB+b,\qquad y=cB+d
$$

朴素展开是：

$$
xy=acB^2+(ad+bc)B+bd
$$

直接递归求 `ac`、`ad`、`bc`、`bd`，会得到四个规模约为一半的乘法：

$$
T(n)=4T(n/2)+O(n)=\Theta(n^2)
$$

Karatsuba 的观察是：

$$
(a+b)(c+d)=ac+ad+bc+bd
$$

令 $z_2=ac$、$z_0=bd$、$z_1=(a+b)(c+d)$，则交叉项可由

$$
ad+bc=z_1-z_2-z_0
$$

恢复。因此只需三次递归乘法：

$$
xy=z_2B^2+(z_1-z_2-z_0)B+z_0
$$

递归式变为：

$$
T(n)=3T(n/2)+O(n)=\Theta(n^{\log_2 3})\approx\Theta(n^{1.585})
$$

减少的不是“几行代码”，而是递归树中每个内部结点的一次子乘法。指数从 2 降到约 1.585，规模很大时差异才会显现。

### C++17 演示：用字符串实现 Karatsuba

为突出算法结构，下面程序处理非负十进制整数，并在较短时退回到朴素竖式乘法。真实高性能大数库通常用二进制机器字、阈值调优及更多乘法算法；字符串实现的常数较大，不应被当作生产级大数库。

```cpp
#include <algorithm>
#include <iostream>
#include <string>
#include <vector>
using namespace std;

string trim(string s) {
    size_t first = s.find_first_not_of('0');
    return first == string::npos ? "0" : s.substr(first);
}

string add(const string& a, const string& b) {
    string result;
    int carry = 0;
    for (int i = static_cast<int>(a.size()) - 1, j = static_cast<int>(b.size()) - 1;
         i >= 0 || j >= 0 || carry; --i, --j) {
        int sum = carry;
        if (i >= 0) sum += a[i] - '0';
        if (j >= 0) sum += b[j] - '0';
        result.push_back(static_cast<char>('0' + sum % 10));
        carry = sum / 10;
    }
    reverse(result.begin(), result.end());
    return result;
}

string subtract(const string& a, const string& b) { // 要求 a >= b
    string result;
    int borrow = 0;
    for (int i = static_cast<int>(a.size()) - 1, j = static_cast<int>(b.size()) - 1;
         i >= 0; --i, --j) {
        int value = (a[i] - '0') - borrow - (j >= 0 ? b[j] - '0' : 0);
        if (value < 0) value += 10, borrow = 1;
        else borrow = 0;
        result.push_back(static_cast<char>('0' + value));
    }
    reverse(result.begin(), result.end());
    return trim(result);
}

string schoolMultiply(const string& a, const string& b) {
    vector<int> digits(a.size() + b.size());
    for (int i = static_cast<int>(a.size()) - 1; i >= 0; --i) {
        for (int j = static_cast<int>(b.size()) - 1; j >= 0; --j) {
            digits[i + j + 1] += (a[i] - '0') * (b[j] - '0');
        }
    }
    for (int i = static_cast<int>(digits.size()) - 1; i > 0; --i) {
        digits[i - 1] += digits[i] / 10;
        digits[i] %= 10;
    }
    string result;
    for (int d : digits) result.push_back(static_cast<char>('0' + d));
    return trim(result);
}

string karatsuba(string x, string y) {
    x = trim(x);
    y = trim(y);
    if (x == "0" || y == "0") return "0";
    if (max(x.size(), y.size()) <= 32) return schoolMultiply(x, y);

    size_t n = max(x.size(), y.size());
    if (n % 2 != 0) ++n;
    x = string(n - x.size(), '0') + x;
    y = string(n - y.size(), '0') + y;
    size_t half = n / 2;

    string a = x.substr(0, half), b = x.substr(half);
    string c = y.substr(0, half), d = y.substr(half);
    string z2 = karatsuba(a, c);
    string z0 = karatsuba(b, d);
    string z1 = karatsuba(add(a, b), add(c, d));
    string middle = subtract(subtract(z1, z2), z0);

    return trim(add(add(z2 + string(2 * half, '0'),
                        middle + string(half, '0')),
                    z0));
}

int main() {
    string x, y;
    cin >> x >> y;
    cout << karatsuba(x, y) << '\n';
}
```

例如输入 `12345678901234567890 98765432109876543210`，程序输出两数乘积。`subtract(z1, z2)` 再减 `z0` 始终合法，因为三者的代数关系保证交叉项非负；不要在不了解这个前提时把字符串减法当成无符号整数减法随意复用。

## 二、Strassen：八次块矩阵乘法如何减为七次

对两个 $n\times n$ 方阵（假设 $n$ 为 2 的幂），按四个大小为 $n/2\times n/2$ 的块划分：

$$
A=\begin{bmatrix}A_{11}&A_{12}\\A_{21}&A_{22}\end{bmatrix},\qquad
B=\begin{bmatrix}B_{11}&B_{12}\\B_{21}&B_{22}\end{bmatrix}
$$

普通块乘法中，每个结果块是两次子矩阵乘法之和，共需要 8 次规模为 $n/2$ 的乘法，递归式为 $T(n)=8T(n/2)+O(n^2)=\Theta(n^3)$。

Strassen 构造七个中间矩阵：

$$
\begin{aligned}
M_1&=(A_{11}+A_{22})(B_{11}+B_{22}) \\
M_2&=(A_{21}+A_{22})B_{11} \\
M_3&=A_{11}(B_{12}-B_{22}) \\
M_4&=A_{22}(B_{21}-B_{11}) \\
M_5&=(A_{11}+A_{12})B_{22} \\
M_6&=(A_{21}-A_{11})(B_{11}+B_{12}) \\
M_7&=(A_{12}-A_{22})(B_{21}+B_{22})
\end{aligned}
$$

再组合为：

$$
\begin{aligned}
C_{11}&=M_1+M_4-M_5+M_7 \\
C_{12}&=M_3+M_5 \\
C_{21}&=M_2+M_4 \\
C_{22}&=M_1-M_2+M_3+M_6
\end{aligned}
$$

于是：

$$
T(n)=7T(n/2)+O(n^2)=\Theta(n^{\log_27})\approx\Theta(n^{2.807})
$$

这里的 $O(n^2)$ 是本层块矩阵加减与拷贝成本。与 Karatsuba 完全一样，七次子乘法取代八次，换来更低的递归指数。

## 三、实现骨架与工程边界

Strassen 的完整工程实现需要处理奇数维度补零、矩阵视图、临时缓冲区复用和数值精度。下面是递归结构的核心骨架；`add`、`sub`、`join` 与普通乘法的实现需保持矩阵维度一致。

```cpp
Matrix strassen(const Matrix& a, const Matrix& b) {
    int n = a.size();
    if (n <= CUTOFF) return ordinaryMultiply(a, b);

    auto [a11, a12, a21, a22] = split(a);
    auto [b11, b12, b21, b22] = split(b);
    Matrix m1 = strassen(add(a11, a22), add(b11, b22));
    Matrix m2 = strassen(add(a21, a22), b11);
    Matrix m3 = strassen(a11, sub(b12, b22));
    Matrix m4 = strassen(a22, sub(b21, b11));
    Matrix m5 = strassen(add(a11, a12), b22);
    Matrix m6 = strassen(sub(a21, a11), add(b11, b12));
    Matrix m7 = strassen(sub(a12, a22), add(b21, b22));

    Matrix c11 = add(sub(add(m1, m4), m5), m7);
    Matrix c12 = add(m3, m5);
    Matrix c21 = add(m2, m4);
    Matrix c22 = add(add(sub(m1, m2), m3), m6);
    return join(c11, c12, c21, c22);
}
```

渐近更快不表示任意规模都更快。Strassen 的矩阵加减、额外内存、递归和缓存行为有很大常数；浮点计算还可能放大舍入误差。因此实际库会设置 `CUTOFF`，小矩阵退回朴素或经过分块优化的矩阵乘法；它也会避免频繁分配子矩阵。算法分析的 $n^{2.807}$ 是规模趋大时的趋势，不是对每个输入尺寸的性能承诺。

## 四、两种算法的共同结构

| 算法 | 朴素子乘法数 | 优化后子乘法数 | 递归式 | 渐近时间 |
| ---- | ------------ | -------------- | ------ | -------- |
| Karatsuba 大整数乘法 | 4 | 3 | $3T(n/2)+O(n)$ | $O(n^{\log_23})$ |
| Strassen 矩阵乘法 | 8 | 7 | $7T(n/2)+O(n^2)$ | $O(n^{\log_27})$ |

两者都不是凭空“少算”。中间量的加减展开后会抵消或恰好重组出原本需要的交叉项。学习时应自己将一个公式展开，逐项验证系数；只背七个 `M` 的符号很难在需要修改或排错时幸存。

## 五、总结

- 分治优化的关键是降低递归子问题数量，不能只看问题是否被均分。
- Karatsuba 用一次和的乘法重建交叉项，将四次半规模乘法降为三次。
- Strassen 用七次块乘法重建四个结果块，将指数从 3 降到约 2.807。
- 更优的渐近复杂度需要同常数、内存、缓存和数值稳定性一起评估；工程实现应有明确的退化阈值。

这两种算法真正值得带走的，不是某组容易遗忘的公式，而是一个设计问题：面对代价昂贵的基本操作时，能否通过重组已有结果，让它少发生一次？分治法在这里给出的答案，通常比“继续把输入切得更细”更有力量。
