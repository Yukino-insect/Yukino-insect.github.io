+++
date = '2026-11-20T21:20:00+08:00'
draft = false
title = '二重积分的变量轮换对称性：为什么 x² 项和 xy 项通常不相等'
math = true
+++

在二重积分中，若积分区域 $D$ 关于直线 $y=x$ 对称，常能利用“交换 $x,y$”简化计算。于是很容易产生一个看似自然、但结论过头的想法：既然 $x$ 与 $y$ 可以轮换，那么 $x^2$ 和 $xy$ 的积分也应相等。

并不如此。**变量轮换对称性只会把一个被积函数变成“交换变量后的函数”，不会把任意含有 $x,y$ 的项彼此等同**。交换 $x,y$ 时，$x^2$ 变成 $y^2$；而 $xy$ 仍然是 $xy$。因此对称性直接给出的是 $x^2$ 项与 $y^2$ 项的积分相等，而不是它们与 $xy$ 项相等。

本文用换元公式、两个反例和一个很有用的平方恒等式，把这件事完整说明。

## 一、先明确：所谓“轮换对称”在做什么

设 $D$ 是平面区域，且交换两个坐标后区域不变：

$$
(x,y)\in D\quad\Longleftrightarrow\quad(y,x)\in D.
$$

这正是“$D$ 关于直线 $y=x$ 对称”的解析表达。令

$$
u=y,\qquad v=x.
$$

这个变换只是把两个坐标互换，其雅可比行列式为：

$$
\frac{\partial(u,v)}{\partial(x,y)}=
\begin{vmatrix}
0&1\\
1&0
\end{vmatrix}=-1,
\qquad
\left|\frac{\partial(u,v)}{\partial(x,y)}\right|=1.
$$

因此面积元不变，即 $dx\,dy=du\,dv$。又因为 $D$ 在这次交换下仍是同一个区域，对任意可积函数 $f$ 都有：

$$
\iint_D f(x,y)\,dx\,dy
=\iint_D f(y,x)\,dx\,dy.
$$

这就是变量轮换对称性的完整结论。注意右侧的函数是 $f(y,x)$；这一步不能省略，更不能把它擅自替换成某个“看起来也很对称”的其他函数。

## 二、分别交换 $x^2$ 与 $xy$

把上面的规则应用到两个常见被积函数，就能看出区别。

### 1. $x^2$ 会变成 $y^2$

取 $f(x,y)=x^2$，交换变量后：

$$
f(y,x)=y^2.
$$

所以：

$$
\iint_D x^2\,d\sigma
=\iint_D y^2\,d\sigma.
$$

这里用 $d\sigma=dx\,dy$ 简记面积元。结论中的对应对象是 $y^2$，因为它确实是 $x^2$ 在变换 $(x,y)\mapsto(y,x)$ 下的像。

### 2. $xy$ 交换后仍是它自己

取 $g(x,y)=xy$，则：

$$
g(y,x)=yx=xy.
$$

变量轮换只会给出：

$$
\iint_D xy\,d\sigma
=\iint_D xy\,d\sigma.
$$

这当然正确，但只是恒等式，没有产生新的数值关系。换句话说，$xy$ 是这次变量交换下的**不变项**；$x^2$ 与 $y^2$ 则是一对被互相交换的项。

可以把三者的命运放在一起看：

| 被积函数 | 交换 $(x,y)\mapsto(y,x)$ 后 | 对称区域上的直接结论 |
| --- | --- | --- |
| $x^2$ | $y^2$ | $\iint_Dx^2\,d\sigma=\iint_Dy^2\,d\sigma$ |
| $y^2$ | $x^2$ | 与上一式相同 |
| $xy$ | $xy$ | 只得到原式本身 |

因此，$x^2$ 与 $xy$ 不在同一条“交换轨道”上。仅凭关于 $y=x$ 的对称性，没有理由要求它们的积分相等。把“变量可交换”理解成“所有二次项都可替换”，正是问题的根源。

## 三、最简单的反例：单位正方形

取最标准的对称区域：

$$
D=[0,1]\times[0,1].
$$

它关于 $y=x$ 对称。直接计算：

$$
\iint_Dx^2\,d\sigma
=\int_0^1\int_0^1x^2\,dy\,dx
=\int_0^1x^2\,dx
=\frac13.
$$

另一方面：

$$
\iint_Dxy\,d\sigma
=\int_0^1\int_0^1xy\,dy\,dx
=\left(\int_0^1x\,dx\right)
 \left(\int_0^1y\,dy\right)
=\frac14.
$$

所以：

$$
\iint_Dx^2\,d\sigma=\frac13\ne\frac14=\iint_Dxy\,d\sigma.
$$

区域已经具有所需的轮换对称性，两个积分仍不相等。一个反例就足够否定“总是相等”的说法，倒也不必让直觉继续替代计算。

## 四、更强的解释：两者之差是一个平方项

对关于 $y=x$ 对称的区域，记：

$$
A=\iint_Dx^2\,d\sigma,
\qquad
B=\iint_Dxy\,d\sigma.
$$

由轮换对称性，$\iint_Dy^2\,d\sigma=A$。展开非负平方 $(x-y)^2$：

$$
\begin{aligned}
\iint_D(x-y)^2\,d\sigma
&=\iint_D\left(x^2-2xy+y^2\right)\,d\sigma\\
&=A-2B+A\\
&=2(A-B).
\end{aligned}
$$

于是得到：

$$
\boxed{
\iint_Dx^2\,d\sigma-\iint_Dxy\,d\sigma
=\frac12\iint_D(x-y)^2\,d\sigma\ge0
}
$$

这个式子比“它们未必相等”更进一步：在积分存在且区域关于 $y=x$ 对称时，$x^2$ 项的积分不小于 $xy$ 项的积分。

### 什么时候才能相等

上式取等号，当且仅当：

$$
(x-y)^2=0
$$

在 $D$ 上几乎处处成立，也就是 $D$ 的绝大部分面积都落在直线 $y=x$ 上。

对于通常意义下有正面积的二维区域，这不可能发生：直线 $y=x$ 的面积为零，区域中总会有 $x\ne y$ 的点，并且通常会占据正面积。因此在这类非退化区域上，实际上有严格不等式：

$$
\iint_Dx^2\,d\sigma>\iint_Dxy\,d\sigma.
$$

这也解释了单位正方形反例不是偶然。$x^2$ 与 $xy$ 的差并非某种难以察觉的算术误差，而是由偏离对角线程度的平方累积而来。

## 五、圆盘的例子：旋转对称也不会使它们相等

有时“轮换对称”会和“绕原点旋转对称”混在一起。即使取单位圆盘：

$$
D=\{(x,y)\mid x^2+y^2\le1\},
$$

它不仅关于 $y=x$ 对称，也关于两条坐标轴对称，并具有任意角度的旋转对称性，结论仍然不是 $x^2$ 与 $xy$ 的积分相等。

用极坐标 $x=r\cos\theta$、$y=r\sin\theta$，其中 $0\le r\le1$、$0\le\theta\le2\pi$，且 $d\sigma=r\,dr\,d\theta$。于是：

$$
\begin{aligned}
\iint_Dx^2\,d\sigma
&=\int_0^{2\pi}\int_0^1r^2\cos^2\theta\cdot r\,dr\,d\theta\\
&=\left(\int_0^1r^3\,dr\right)
  \left(\int_0^{2\pi}\cos^2\theta\,d\theta\right)
=\frac\pi4.
\end{aligned}
$$

而：

$$
\begin{aligned}
\iint_Dxy\,d\sigma
&=\int_0^{2\pi}\int_0^1r^2\cos\theta\sin\theta\cdot r\,dr\,d\theta\\
&=\left(\int_0^1r^3\,dr\right)
  \left(\int_0^{2\pi}\cos\theta\sin\theta\,d\theta\right)
=0.
\end{aligned}
$$

这里 $xy$ 的积分为零，原因也不是它与 $x^2$ 相同，而是 $xy$ 对 $x$ 轴或 $y$ 轴是奇函数。例如关于 $x$ 轴的反射 $(x,y)\mapsto(x,-y)$ 会把 $xy$ 变为 $-xy$，正负两部分完全抵消；$x^2$ 在该反射下仍为 $x^2$，不会发生这种抵消。

## 六、解题时应先问：是哪一种对称变换

面对对称积分，可靠的步骤不是先猜某几项“应该相等”，而是明确写出变换，并逐项代入。常用情形如下：

| 区域保持不变的变换 | 被积函数的变化 | 常见用途 |
| --- | --- | --- |
| $(x,y)\mapsto(y,x)$ | $x^2\leftrightarrow y^2$，$xy\mapsto xy$ | 令 $\iint x^2=\iint y^2$ |
| $(x,y)\mapsto(x,-y)$ | $xy\mapsto-xy$，$x^2\mapsto x^2$ | 推出 $\iint xy=0$ |
| $(x,y)\mapsto(-x,y)$ | $xy\mapsto-xy$，$y^2\mapsto y^2$ | 推出 $\iint xy=0$ |
| $(x,y)\mapsto(-x,-y)$ | $x^2,y^2,xy$ 都不变 | 通常不能直接让这些二次项为零或彼此相等 |

最后一行尤其值得注意：关于原点的中心对称只会消去总次数为奇数的项，例如 $x$、$y$、$x^2y$；$x^2$ 和 $xy$ 的总次数都是偶数，在中心反射下不变，所以不能据此得到零积分或相等关系。

## 七、总结

二重积分中的对称性是一条换元规则，不是一张可以随意替换符号的许可证。

- 若 $D$ 关于 $y=x$ 对称，则 $\iint_Df(x,y)\,d\sigma=\iint_Df(y,x)\,d\sigma$。
- 对 $f=x^2$，轮换后的函数是 $y^2$，故 $\iint_Dx^2\,d\sigma=\iint_Dy^2\,d\sigma$。
- 对 $f=xy$，轮换后仍是 $xy$，因此轮换对称性不会把它与 $x^2$ 联系起来。
- 更准确地说，$\iint_Dx^2\,d\sigma-\iint_Dxy\,d\sigma=\frac12\iint_D(x-y)^2\,d\sigma$；对通常的正面积对称区域，前者严格大于后者。

以后遇到“区域对称，所以某两项积分相等”的推导时，只要做一次检验：把第一个被积函数中的 $x,y$ 按该对称变换逐一替换，看看它究竟变成了谁。若结果不是第二个被积函数，那么这条相等式就还缺少额外条件，不能因为形式上长得相似就被判为同一个对象。
