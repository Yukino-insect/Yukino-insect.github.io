+++
date = '2026-10-13T20:00:00+08:00'
draft = false
title = 'PyTorch 训练进阶：优化器、批训练、正则化与训练稳定性'
math = true
+++

上一节已经完成了一个能更新参数的训练循环。不过，能运行只是起点：同一组数据换一个学习率、batch 大小或优化器，训练速度和最终效果都可能不同。本篇解释这些选择各自改变什么，以及怎样让训练过程稳定、可比较。

## 先补齐一条数学主线：损失、导数与梯度

优化器并不知道“分类正确”或“图像看起来更好”是什么意思；它只能读取一个可微的**损失函数**并调整参数。把模型的所有可学习数拼成向量 $\theta$，把一个 batch 的输入和标签记为 $(x, y)$。模型先计算预测 $\hat y=f_\theta(x)$，损失函数再把“预测与标签相差多少”压缩为一个标量：

$$
L(\theta)=\operatorname{loss}(f_\theta(x), y)
$$

这里 $L$ 是当前 batch 的平均损失，$f_\theta$ 是由参数 $\theta$ 决定的模型，$x$ 是输入，$y$ 是真实标签，$\hat y$ 是预测。训练的目标不是让某一次输出“恰好好看”，而是寻找一组参数，让许多 batch 上的 $L(\theta)$ 都较小。

只有一个参数时，导数 $\frac{dL}{d\theta}$ 描述参数向右增加一点点时损失的瞬时变化率：导数为正，增大参数会让损失上升；导数为负，增大参数反而会让损失下降。多个参数时，每个参数各有一个偏导数，按原顺序组成**梯度**：

$$
\nabla_\theta L=
\left[
\frac{\partial L}{\partial\theta_1},
\frac{\partial L}{\partial\theta_2},
\ldots,
\frac{\partial L}{\partial\theta_d}
\right]
$$

$d$ 是参数个数，$\theta_j$ 是第 $j$ 个参数。梯度指向局部上升最快的方向，因此其相反方向是局部下降最快的方向；这就是更新式里总有负号的原因。它只是当前位置附近的一阶近似，损失面很弯曲或步长过大时，并不保证走一步后一定下降。

例如令 $L(w)=(w-3)^2$，其中 $w$ 是一个标量参数，目标值为 3。展开并求导得到：

$$
\frac{dL}{dw}=2(w-3)
$$

当 $w=1$ 时，损失为 $(1-3)^2=4$，梯度为 $2(1-3)=-4$。负梯度是 4，说明应把 $w$ 增大；若学习率 $\eta=0.1$，最普通的一步更新为 $w\leftarrow1-0.1\times(-4)=1.4$，新损失变为 $2.56$。这个小例子也给出了一条以后可反复使用的判断：梯度给方向和局部变化尺度，学习率决定是否只走一小步。

在 PyTorch 中，`loss.backward()` 用自动微分把这些偏导数写入每个可训练 `nn.Parameter` 的 `.grad`；它计算梯度，但不会改变 `.data` 中的参数值。随后 `optimizer.step()` 才读取这些梯度并执行某种更新规则。下面讨论的所有优化器，都是在决定“怎样把梯度变成真正的参数改变量”。

## 一个 epoch 中究竟发生了多少次更新

训练通常不把整个训练集一次塞进模型，而是按 **mini-batch（小批量）** 逐批处理。若训练集有 $N$ 条样本、`batch_size` 为 $B$，一轮完整遍历训练集大约会执行：

$$
\left\lceil\frac{N}{B}\right\rceil
$$

次参数更新。完整遍历一次训练集叫作一个 **epoch**，而 `optimizer.step()` 执行一次才是一条 **step**。两者不是同一个计数单位；把 3,200 条样本按每批 32 条送入模型，一个 epoch 约有 100 个 step。

小批量是现实中的折中：逐条更新噪声大、吞吐低；全量计算梯度稳定，却常常放不进显存，也会让一次等待太久。mini-batch 能利用 CPU/GPU 并行，同时保留适度的梯度噪声。`batch_size` 变大时通常需要更多内存；它并不保证一定更准或更快收敛。

### 全量梯度究竟“更准确”在哪里

先把“准确”拆开。设训练集中有 $N$ 条样本，第 $i$ 条样本的损失是 $\ell_i(\theta)$，其中 $\theta$ 为当前全部模型参数；训练集经验风险（也就是训练样本平均损失）为：

$$
J_N(\theta)=\frac{1}{N}\sum_{i=1}^{N}\ell_i(\theta)
$$

全量梯度为：

$$
g_{full}=\nabla J_N(\theta)=\frac{1}{N}\sum_{i=1}^{N}\nabla\ell_i(\theta)
$$

对**固定的训练集和固定参数**而言，它就是这份训练集平均损失的精确梯度；每次重新计算都相同，所以更新方向稳定。它并不是“对真实世界总体规律的精确梯度”——训练集本身也只是总体的一个有限样本。

若从训练集均匀随机抽取大小为 $B$ 的 mini-batch $\mathcal B$，并使用 `mean` reduction，则：

$$
g_{batch}=\frac{1}{B}\sum_{i\in\mathcal B}\nabla\ell_i(\theta),
\qquad
\mathbb E[g_{batch}]=g_{full}
$$

其中 $\mathcal B$ 是本次抽到的样本下标集合，$|\mathcal B|=B$；$\nabla\ell_i(\theta)$ 是第 $i$ 条样本对所有参数产生的梯度。也就是说，小批量梯度通常是全量训练集梯度的**无偏估计**：平均很多次后会指向相同方向，但单次会因抽到哪些样本而波动。样本近似独立时，batch 均值的方差大致随 $1/B$ 降低；batch 越大，单次估计越接近全量梯度，显存和每步等待也越大。

下面用四条样本的“单样本梯度”做数值例子。假设当前参数处，这四个梯度分别为 `[-6, -2, 2, 10]`：

```python
import torch

per_example_grad = torch.tensor([-6.0, -2.0, 2.0, 10.0])
print('全量梯度：', per_example_grad.mean().item())  # 1.0

for indices in ([0, 1], [0, 2], [2, 3]):
    batch_grad = per_example_grad[indices].mean()
    print(indices, batch_grad.item())  # -4.0、-2.0、6.0
```

每个小批量的方向甚至可能与全量梯度不同；这正是“噪声”。但如果随机抽取很多 batch 并取平均，结果会回到 1。loss 也是同样关系：使用 `reduction='mean'` 的 batch loss 是全量平均训练 loss 的估计，而不是天然更小或更大的一种“不同单位”。

因此应得出的结论不是“全量一定更好”，而是：全量对当前训练集更稳定、每次更新次数更少；小批量的单步更嘈杂、更新更频繁、硬件利用率更高，且噪声有时能帮助跳出狭窄区域。实际效果还受学习率、数据顺序、模型、归一化层和总训练 step 数共同影响。

## 参数、超参数与优化器各管什么

不要把模型自己学到的数和人设定的训练策略混为一谈。

| 名称 | 谁决定 | 例子 | 作用 |
| ---- | ------ | ---- | ---- |
| 参数 | 训练过程更新 | 权重、偏置 | 决定模型具体怎样计算 |
| 超参数 | 人或实验策略设定 | 学习率、batch 大小、层数 | 决定学习过程与模型容量 |
| 优化器 | 人选择、代码执行 | SGD、AdamW | 根据梯度更新参数 |
| epoch | 训练循环计数 | `epochs=20` | 表示完整遍历训练集的次数 |

最基本的 SGD 沿当前梯度的反方向走一步。Momentum 会积累一段时间的更新方向，以减弱来回震荡；Adam 会根据历史梯度为不同参数调整更新尺度；**AdamW** 则将权重衰减与 Adam 的自适应更新分开处理，是许多现代任务可靠的起点。

```python
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=3e-3,
    weight_decay=1e-4,
)
```

这不是“最优模板”。视觉任务中仔细调参后的 SGD + Momentum 也常有良好表现；小型教学模型用 Adam 也完全合理。先明确任务、数据规模和可观察的验证指标，再比较方案。否则只是在为一个尚未定义清楚的问题挑选更华丽的方向盘。

## 优化器到底读取和保存了什么

优化器并不负责求导。`loss.backward()` 已经将每个 `nn.Parameter` 的梯度写入 `parameter.grad`；创建优化器时，`model.parameters()` 将注册参数交给它；`optimizer.step()` 才根据梯度和自己保存的历史状态修改参数。对象关系如下：

```text
nn.Module 注册的 Parameter
        ↓ model.parameters()
optimizer.param_groups
        ↓ loss.backward()
每个 Parameter.grad
        ↓ optimizer.step()
Parameter 的数值 + optimizer.state 中的历史统计
```

### SGD：最直接的基线

无动量 SGD 的更新是：

$$
\theta_{t+1}=\theta_t-\eta g_t
$$

下标 $t$ 表示第 $t$ 次参数更新，$\theta_t$ 是更新前的参数向量，$g_t=\nabla_\theta L_t(\theta_t)$ 是当前 batch 损失 $L_t$ 在 $\theta_t$ 处的梯度，$\eta>0$ 是学习率。按元素理解即可：若某个参数当前为 2、对应梯度是 3、`lr=0.1`，更新后就是 $2-0.1\times3=1.7$；若梯度是 -3，则更新为 2.3。由此可以直接预测 PyTorch 代码的行为：在没有动量和权重衰减时，`SGD(..., lr=0.1)` 的 `step()` 会让每个参数沿自己 `.grad` 的反方向移动 `0.1 × grad`。

它没有记忆，因而容易理解；但在狭长损失谷中，梯度会在陡峭方向来回摆动，向真正需要前进的方向移动缓慢。SGD 的“随机”来自每次使用随机 mini-batch，并不是更新式额外掷骰子；若每次都用全量训练集，它就成为普通的全批量梯度下降。

### Momentum：让更新具有惯性

动量法引入速度 $v_t$：

$$
v_t=\mu v_{t-1}+g_t,
\qquad
\theta_{t+1}=\theta_t-\eta v_t
$$

`μ` 常取接近 1 的值，例如 0.9。若多个 batch 的梯度方向一致，速度累积；若只是单个 batch 的随机抖动，正负更新会部分抵消。它不是“自动更聪明”，而是明确假设近期方向具有参考价值。

例如一维参数初始 $\theta_0=10$、$v_0=0$、$\eta=0.1$、$\mu=0.9$，连续两个 batch 的梯度都为 $g_1=g_2=2$。第一次有 $v_1=2$、$\theta_1=10-0.1\times2=9.8$；第二次有 $v_2=0.9\times2+2=3.8$、$\theta_2=9.8-0.1\times3.8=9.42$。相比没有动量时第二步只再移动 0.2，动量使持续一致的方向走了 0.38。反过来，若第二个梯度为 -2，则 $v_2=1.8-2=-0.2$，更新很小，短期反向噪声被缓冲。不同框架可能在动量的初值、Nesterov 细节上略有实现差别；理解 `torch.optim.SGD` 的精确选项时应以其文档和当前版本为准，不应把这个教学式当成所有变体的逐字实现。

```python
optimizer = torch.optim.SGD(
    model.parameters(), lr=1e-2, momentum=0.9, weight_decay=1e-4
)
```

### Adam：为每个参数估计步长

Adam 对每个参数梯度维护一阶矩（类似平滑方向）和二阶矩（梯度平方的平滑尺度）：

$$
m_t=\beta_1m_{t-1}+(1-\beta_1)g_t
$$

$$
v_t=\beta_2v_{t-1}+(1-\beta_2)g_t^2
$$

这里的 $m_t$ 是梯度的指数滑动平均（一阶矩），$v_t$ 是梯度**逐元素平方**的指数滑动平均（二阶原始矩）；$\beta_1$ 与 $\beta_2$ 在 $[0,1)$ 中控制历史保留程度，$g_t^2$ 不是矩阵乘法，而是每一个参数梯度各自平方。由于 $m_0=v_0=0$，训练刚开始时它们被零拉低，所以 Adam 还使用：

$$
\hat m_t=\frac{m_t}{1-\beta_1^t},
\qquad
\hat v_t=\frac{v_t}{1-\beta_2^t},
\qquad
\theta_{t+1}=\theta_t-\eta\frac{\hat m_t}{\sqrt{\hat v_t}+\epsilon}
$$

$\hat m_t$、$\hat v_t$ 是偏差修正后的统计量，$\epsilon$ 是防止分母为零的很小正数；除法、平方根同样逐元素进行。举一个第一步就能算清的例子：令某个参数 $\theta_0=5$、$g_1=4$、$\beta_1=0.9$、$\beta_2=0.999$、$\eta=0.001$，暂时忽略极小的 $\epsilon$。则 $m_1=0.1\times4=0.4$，$v_1=0.001\times4^2=0.016$；修正后 $\hat m_1=0.4/(1-0.9)=4$，$\hat v_1=0.016/(1-0.999)=16$，更新量为 $0.001\times4/\sqrt{16}=0.001$，所以参数变为约 4.999。这个例子揭示了 Adam 的特性：第一步中梯度的绝对值在分子、分母大致抵消，更新尺度主要由 `lr` 决定；长期训练中，各参数的历史梯度尺度不同，步长才会分化。

直觉上，持续且稳定的方向得到较明确的更新；梯度尺度很大的参数会被相对缩小步长。这不意味着 Adam 保证更快、更好地泛化，也不意味着能替代学习率调参。常见默认 `betas=(0.9, 0.999)`、`eps=1e-8` 并非定律，而是经验起点。

### AdamW：把权重衰减从自适应更新中分离

L2 正则化常写为损失中加入 $\lambda\|\theta\|^2$。对普通 SGD，它与每次将参数向 0 轻微拉回的 weight decay 近似等价；在 Adam 的逐参数自适应缩放下，这个等价不再自然成立。AdamW 显式执行衰减，再执行 Adam 更新，因而现代 Transformer 等模型常优先使用它：

$$
\theta_{t+1}=(1-\eta\lambda)\theta_t-\eta\operatorname{AdamStep}(g_t)
$$

向量范数平方是 $\|\theta\|^2=\sum_{j=1}^{d}\theta_j^2$，$\lambda\geq0$ 是正则强度。若把正则项准确写成 $\lambda\|\theta\|^2$，它对参数的梯度是 $2\lambda\theta$；不少库或教材改写为 $\frac{\lambda}{2}\|\theta\|^2$，以便梯度写成 $\lambda\theta$。因此看到公式时必须确认系数约定，不能只凭“L2”三个字比较数值。PyTorch 的 `weight_decay` 定义的是优化器选项，而不等同于要求你手工把某一种系数形式加进 `loss`。

对上面的 AdamW 更新式，若某个参数为 10、`lr=0.001`、`weight_decay=0.1`，先乘衰减因子 $1-0.001\times0.1=0.9999$，会变为 9.999；再叠加由梯度得到的 Adam 更新。它解释了两个实际现象：即使当前数据梯度为零，启用 weight decay 的参数也会缩小；而 `lr` 降低时，每一步的衰减也会变弱。总的正则强度还取决于训练了多少 step，不能脱离训练时长只比较一个 `weight_decay` 数字。

不是所有参数都适合衰减。实践中常将 bias、LayerNorm/BatchNorm 的缩放参数排除，形成两个 parameter group：

```python
decay, no_decay = [], []
for name, parameter in model.named_parameters():
    if not parameter.requires_grad:
        continue
    (no_decay if name.endswith('bias') or 'norm' in name.lower() else decay).append(parameter)

optimizer = torch.optim.AdamW([
    {'params': decay, 'weight_decay': 1e-4},
    {'params': no_decay, 'weight_decay': 0.0},
], lr=3e-4)
```

这不是所有架构都必须照抄的名单，而是展示 parameter group 的用途：同一个优化器可对不同参数集合使用不同学习率、权重衰减或其他设置。

### 查看优化器的真实状态

第一次 `step()` 前 AdamW 几乎没有每参数历史；执行一次更新后可以查看：

```python
state = optimizer.state_dict()
print(state['param_groups'])  # 学习率、weight_decay 和参数组配置
print(state['state'])         # 每个参数的 step、exp_avg、exp_avg_sq 等
```

这里的键会以参数 ID 等内部标识组织，不适合手动编辑；但它解释了为什么断点续训不仅要加载 `model.state_dict()`，也要加载 `optimizer.state_dict()`。否则参数数值相同，动量/矩估计却从零开始，接下来的训练轨迹会改变。

## 学习率：最值得先检查的旋钮

学习率 `lr` 决定每次参数更新迈多大步。它太大时，loss 可能剧烈震荡、发散，甚至出现 `NaN`；它太小时，loss 虽然不报错却长期几乎不动。训练不佳时，学习率通常比“再叠两层网络”更值得优先检查。

不要把“调学习率”理解成凭感觉改一个神秘数字。先用一个只有一个参数的函数观察步长：

```python
import torch

for lr in (0.01, 0.2, 1.0):
    w = torch.tensor(0.0, requires_grad=True)
    for _ in range(5):
        loss = (w - 3) ** 2
        loss.backward()
        with torch.no_grad():
            w -= lr * w.grad
        w.grad.zero_()
    print(lr, round(w.item(), 3), round(loss.item(), 3))
```

梯度在这里是 $2(w-3)$，负梯度方向把 `w` 推向目标 3；`lr` 只决定每次走多远。较小的值靠近得慢，过大的值可能越过目标来回震荡。这个最小实验不能替代真实任务的搜索，但它把“学习率影响训练轨迹”变成了可以观察的事实。

这个二次函数还能给出可计算的边界。令误差 $e_t=w_t-3$，把梯度代入 SGD 更新式可得：

$$
e_{t+1}=(1-2\eta)e_t
$$

当 $0<\eta<1$ 时，$|1-2\eta|<1$，误差会逐步缩小；$0<\eta<0.5$ 时它从同一侧平滑靠近，$0.5<\eta<1$ 时会越过目标但振幅仍减小；$\eta=1$ 时误差在正负之间原样跳动，$\eta>1$ 时振幅反而增大。比如从 $w_0=0$ 出发，`lr=0.2` 时 $e_1=(1-0.4)\times(-3)=-1.8$，即 $w_1=1.2$；`lr=1.2` 时 $e_1=(1-2.4)\times(-3)=4.2$，即 $w_1=7.2$，已经比起点离目标更远。真实深度网络不是单一二次函数，不能据此算出万能学习率，但这正是它的用途：用局部曲率不同来理解为什么同一个 `lr` 在某层很温和、在另一层却可能发散。

实用做法是从一个保守值起步，只改一个变量并观察训练/验证曲线。例如在当前课程的小 MLP 中，可依次试 `1e-2`、`1e-3`、`3e-4`，而不是同时更换模型、batch、数据增强和优化器。实验若一次改动五处，结果再漂亮也无法说明究竟是谁起了作用。

训练后期往往需要更小的步长来细化收敛。常见调度策略包括按固定 epoch 衰减、余弦衰减，以及验证指标长期无改善时降低学习率：

```python
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer,
    mode='min',
    factor=0.5,
    patience=2,
)

# 每轮验证后传入验证集损失，而不是训练集损失。
scheduler.step(valid_loss)
```

调度器只能调整步长，不能修复标签错位、数据泄漏或损失函数不匹配。先确保训练对象正确，再讨论怎样走得更优雅；顺序颠倒时，耐心通常只会被浪费得更久。

## 正则化：防止死记硬背，而不是万能加分项

训练集表现很好、验证集却明显变差时，模型可能正在过拟合。常见的缓解手段如下。

| 方法 | 核心做法 | 适合先考虑的场景 |
| ---- | -------- | ---------------- |
| 权重衰减 | 抑制权重过大 | 常规 MLP、CNN、Transformer 训练 |
| Dropout | 训练时随机暂时屏蔽部分特征 | 全连接层较多、验证差距明显时 |
| 数据增强 | 改变样本外观但保持标签 | 图像、语音等标签不随变换改变的任务 |
| 早停 | 验证集长期无改善时停止 | epoch 较多、需防止继续记忆训练集时 |
| 减小模型 | 降低表达能力 | 数据量有限且模型明显过大时 |

`weight_decay` 并非“越大越防过拟合”。如果训练集本身都学不好，增加 Dropout 或权重衰减只会进一步限制模型。处理顺序应是：先确认任务、标签、切分和训练循环；再根据训练/验证曲线判断欠拟合还是过拟合；最后选择有针对性的正则化手段。

### Dropout：训练时制造扰动，推理时恢复确定性

Dropout 不是删除模型参数，而是在**训练阶段**随机把一部分激活置零。设上一层某个激活为 $h$，丢弃概率为 $p$，保留概率为 $q=1-p$；令随机掩码 $r\sim\operatorname{Bernoulli}(q)$，其中 $r=1$ 表示保留、$r=0$ 表示丢弃。PyTorch 默认使用 inverted dropout：

$$
\tilde h=\frac{r}{q}h
$$

因为 $\mathbb E[r]=q$，所以 $\mathbb E[\tilde h]=\frac{\mathbb E[r]}{q}h=h$。也就是说，训练时虽有随机性，激活的期望尺度与不使用 Dropout 时一致；推理的 `model.eval()` 下不再随机置零，也不再额外乘缩放系数。

例如 `nn.Dropout(p=0.25)` 有 $q=0.75$。一个激活 $h=8$ 被保留时输出 $8/0.75\approx10.67$，被丢弃时输出 0；单次输出不是 8，但长期平均为 $0.75\times10.67+0.25\times0=8$。这也解释了为什么相同输入在 `model.train()` 下多次前向可能不同、在 `model.eval()` 下应稳定一致。Dropout 对过拟合可能有帮助，却会让训练损失更难下降；它不是数据量不足、标签错误或训练/验证分布不一致的修复工具。

### BatchNorm：训练时统计当前 batch，推理时使用历史统计量

**Batch Normalization（批归一化，简称 BatchNorm）** 是一个有可学习参数、也有非参数状态的层。它解决的问题不是“随机删掉特征”——那是 Dropout 的职责——而是让某层的激活在训练时按当前 batch 的统计量重新定标，使后续层面对的数值尺度更稳定。

对一个特征通道的一批数 $x_1,\ldots,x_m$，训练前向先计算当前 batch 的均值和方差：

$$
\mu_B=\frac{1}{m}\sum_{i=1}^{m}x_i,\qquad
\sigma_B^2=\frac{1}{m}\sum_{i=1}^{m}(x_i-\mu_B)^2
$$

再标准化并进行可学习的缩放、平移：

$$
\hat{x}_i=\frac{x_i-\mu_B}{\sqrt{\sigma_B^2+\varepsilon}},\qquad
y_i=\gamma\hat{x}_i+\beta
$$

其中 $m$ 是参与统计的元素数，$\varepsilon$ 是防止除以零的小常数；$\gamma$ 和 $\beta$ 是由优化器更新的 `nn.Parameter`。例如某一通道在两个样本中的值为 `[2, 4]`，则 $\mu_B=3$、$\sigma_B^2=1$，忽略很小的 $\varepsilon$ 后，标准化结果为 `[-1, 1]`。初始化时通常 $\gamma=1$、$\beta=0$，所以输出仍约为 `[-1, 1]`；训练可以把 $\gamma$ 和 $\beta$ 学成别的值，BatchNorm 并不会强迫网络最终输出必须均值为 0、方差为 1。

它在不同输入形状上的“一个通道”并不相同：

| 层 | 常见输入 shape | 统计范围 |
| --- | -------------- | -------- |
| `nn.BatchNorm1d(C)` | `[N,C]` 或 `[N,C,L]` | 每个通道分别跨 batch（及存在时的长度维）统计 |
| `nn.BatchNorm2d(C)` | `[N,C,H,W]` | 每个通道分别跨 `N`、`H`、`W` 统计 |

因此卷积特征图常写成“卷积 → `BatchNorm2d` → 激活函数”：同一输出通道的所有样本和空间位置共同给出统计量。一个最小 MLP 可以这样放置：

```python
import torch
from torch import nn

class NormalizedClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.hidden = nn.Linear(2, 8)
        self.norm = nn.BatchNorm1d(8)
        self.activation = nn.ReLU()
        self.output = nn.Linear(8, 1)

    def forward(self, x):
        x = self.hidden(x)      # [N, 2] -> [N, 8]
        x = self.norm(x)        # 每个隐藏通道按 BatchNorm1d 的约定处理
        x = self.activation(x)
        return self.output(x).squeeze(1)
```

这里的 `norm.weight` 与 `norm.bias` 分别就是 $\gamma$、$\beta$，会出现在 `model.parameters()` 中；而 `running_mean`、`running_var` 是随着训练更新、需要保存和迁移 device、却不该由优化器更新的 **buffer**。这正好把前文的 `Parameter` 与 buffer 的区别落到一个真实层上。

`model.train()` 与 `model.eval()` 因而不是可有可无的仪式：

- 训练模式：BatchNorm 用**当前 batch**的统计量完成这次前向，同时用滑动方式更新 `running_mean` 和 `running_var`；Dropout 也在这个模式随机屏蔽激活。
- 评估/推理模式：BatchNorm 改用训练期间累计的运行统计量，不再因“这次恰好同 batch 的其他样本是谁”而改变结果；Dropout 同时关闭随机屏蔽。

```python
layer = nn.BatchNorm1d(2)
x = torch.tensor([[2.0, 10.0], [4.0, 14.0]])

layer.train()
train_output = layer(x)  # 使用当前 x 的每个通道统计量，并更新 running_* buffer

layer.eval()
eval_output = layer(x)   # 使用累计的 running_mean / running_var

print(train_output)
print(eval_output)       # 通常与 train_output 不同，这不是随机错误
print(layer.running_mean, layer.running_var)
```

训练 batch 很小时，当前 batch 的均值和方差本身就很不稳定；例如 `BatchNorm1d` 的二维输入若 batch size 为 1，训练时甚至可能无法得到有意义的每通道方差。此时应考虑增大有效 batch、冻结已有 BatchNorm 的运行统计量，或按任务改用 LayerNorm / GroupNorm；不能只把 `model.eval()` 塞进训练循环来“消除报错”，那会使参数梯度与统计状态不再遵循原来的训练设计。Transformer 常用 LayerNorm，正是因为它按单个样本的特征维归一化，不依赖 batch 中其他样本；它不是 BatchNorm 的拼写变体。

## 训练模式、梯度裁剪与数值稳定性

有 Dropout 或 BatchNorm 时，训练和验证必须显式切换模式。训练时 `model.train()` 让 Dropout 生效、BatchNorm 使用当前 batch 的统计量；验证与推理时 `model.eval()` 关闭 Dropout，并改用累计的运行统计量。再配合 `torch.inference_mode()`，验证阶段既不更新参数，也不记录反向传播所需的计算图。

对 RNN、深网络或不稳定任务，梯度偶尔会异常大。梯度裁剪会限制更新前的总梯度范数：

```python
optimizer.zero_grad(set_to_none=True)
logits = model(features)
loss = loss_fn(logits, labels)
loss.backward()

torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
optimizer.step()
```

把所有参数梯度首尾拼接为向量 $g$，其 L2 范数为 $\lVert g\rVert_2=\sqrt{\sum_j g_j^2}$。当该范数超过阈值 $c$ 时，`clip_grad_norm_` 等价于按同一比例缩放所有梯度：

$$
g_{\text{clipped}}=
g\times\min\left(1,\frac{c}{\lVert g\rVert_2}\right)
$$

它保留梯度整体方向，只限制长度。举例说两个参数的梯度为 $(6,8)$，总范数是 $\sqrt{6^2+8^2}=10$；`max_norm=1` 时乘以 $1/10$，裁剪后为 $(0.6,0.8)$。若范数本来是 0.5，则乘数为 1，完全不变。因此它发生在 `loss.backward()` 写好 `.grad` 之后、`optimizer.step()` 读取 `.grad` 之前；放在 `step()` 之后不会挽回已经发生的大更新。范数裁剪也不等于“让每个梯度绝对值不超过阈值”，后者是 `clip_grad_value_` 的另一种逐元素策略。

它适合处理梯度爆炸风险，但不该用来掩盖所有 `NaN`。数值不稳定通常来自有限精度下的非法或极端运算：除以接近零的标准差、`exp(z)` 在很大正 $z$ 时上溢、`log(0)`、学习率过大导致参数逐步放大，都会产生 `Inf`，后续计算再传播为 `NaN`。例如二分类的概率形式损失含有 $-\log(p)$；若先用低精度手动计算 sigmoid，极端 logit 可能让 $p$ 舍入为 0 或 1，接着取对数就失去精度。`BCEWithLogitsLoss` 直接接收未经过 sigmoid 的 logits，并以稳定的等价变形计算，通常比“先 `sigmoid` 再 `BCELoss`”可靠。

遇到 `NaN` 或 `Inf` 时，先在发生位置检查 `torch.isfinite()`，并按数据流排查输入和标签、标准化除数、学习率、损失函数的数值稳定版本，以及混合精度下模型与输入的 dtype。若是混合精度训练，还应按其训练流程先对梯度 unscale 再裁剪；否则被放大的梯度范数会让裁剪阈值失去原有含义。裁剪只能限制有限但过大的梯度，不能把已经是 `NaN` 的数“修好”。

## 保存“最好的一轮”，而不是最后一轮

训练 loss 持续下降，并不意味着验证效果也持续变好。因此应以验证指标决定 checkpoint，而不是默认保存最后一个 epoch：

```python
best_valid_loss = float('inf')

for epoch in range(epochs):
    # 此处执行训练，并计算 valid_loss。
    if valid_loss < best_valid_loss:
        best_valid_loss = valid_loss
        torch.save(model.state_dict(), 'best-model.pt')
```

真实工程中还应同时保存模型配置、优化器状态、epoch、随机种子和数据版本。单独留下一个权重文件，往往不足以解释它为何有效，更无法稳妥地重现实验。

## 小结

- 一个 epoch 包含多个 batch 和多个 `optimizer.step()`；batch 大小同时影响内存、吞吐和梯度噪声。
- 优化器决定如何使用梯度，学习率决定每步多远；先一次只调整一个变量。
- 正则化用于处理过拟合，不能挽救还没学会训练集的模型。
- `train()` / `eval()`、数值稳定损失、梯度裁剪和最佳 checkpoint，是可靠训练循环的基本边界。

下一篇将讨论如何判断模型是否真的有用：Accuracy、Precision、Recall、F1 与阈值该怎样依据错误代价选择。
