+++
date = '2025-12-14T20:06:31+08:00'
draft = false
title = '二叉搜索树查找第k大的元素'

+++

二叉搜索树满足以下条件：

- 对于根节点，左子树中所有节点的值 < 根节点的值 < 右子树中所有节点的值。
- 任意节点的左右子树也是二叉搜索树，即同样满足上一条件。

## 查找节点

二叉树的查找操作和二分查找的原理一致，都是每次排除一半。

```java
class TreeNode {

    int val;
    TreeNode left;
    TreeNode right;

    TreeNode(int x) {
        val = x;
    }
}

public class BinarySearchTree {

    private static TreeNode search(TreeNode root, int num) {
        if (root == null) {
            return null;
        }
        if (root.val == num) {
            return root;
        }
        TreeNode cur = root;
        while (cur != null) {
            // 如果当前值等于目标值，跳出循环
            if (cur.val == num) {
                break;
            }
            // 如果当前值小于目标值，当前节点等于更大的右节点
            // 如果当前值大于目标值，当前节点等于更小的左节点
            if (cur.val < num) {
                cur = cur.right;
            } else {
                cur = cur.left;
            }
        }
        return cur;
    }
}
```

二叉搜索树的插入操作，注意插入时如果判断有与 `val` 相同的值，直接返回。二叉搜索树不允许有重复值

```java
private static void insert(TreeNode root, int val) {
    // 如果当前 root 为空，直接将 val 作为根节点
    if (root == null) {
        root = new TreeNode(val);
        return;
    }
    TreeNode cur = root, prev = null;
    // 查询插入的位置
    while (cur != null) {
        // 二叉搜索树不允许右重复节点，找到重复节点直接返回
        if (cur.val == val) {
            return;
        }
        // 保存 cur 的上一个节点
        prev = cur;
        if (cur.val < val) {
            // 如果当前值节点的值小于插入值，那么插入值在右子树
            cur = cur.right;
        } else {
            // 如果当前节点的值大于插入值，那么插入值在左子树
            cur = cur.left;
        }
    }
    // 因为这时 cur 节点为空，跳出循环。现在判断 val 该插入 prev 的那个位置
    if (prev.val < val) {
        // 如果当前节点的值小于插入值，插入值在右侧
        prev.right = new TreeNode(val);
    } else {
        // 如果当前节点的值大于插入值，插入值在左侧
        prev.left = new TreeNode(val);
    }
}
```

删除节点

在执行删除操作时需要分情况。

- 如果是叶子节点，直接删掉即可
- 如果是非叶子节点，删除的时候需要考虑二叉搜索树的整体的平衡

```java
private static void remove(TreeNode root, int val) {
    if (root == null) {
        return;
    }
    TreeNode cur = root, prev = null;
    // 查询指定节点位置
    while (cur != null) {
        if (cur.val == val) {
            break;
        }
        prev = cur;
        if (cur.val < val) {
            cur = cur.right;
        } else {
            cur = cur.left;
        }
    }
    // 若无待删除节点，直接返回
    if (cur == null) {
        return;
    }
    // 子节点数量 = 0 or 1
    if (cur.left == null || cur.right == null) {
        // 当子节点数量 = 0 / 1 时， child = null / 该子节点
        TreeNode child = cur.left != null ? cur.left : cur.right;
        // 删除节点 cur
        if (cur != root) {
            if (prev.left == cur)
                prev.left = child;
            else
                prev.right = child;
        } else {
            // 若删除节点为根节点，则重新指定根节点
            root = child;
        }
    }
    // 子节点数量 = 2
    else {
        // 获取中序遍历中 cur 的下一个节点
        TreeNode tmp = cur.right;
        while (tmp.left != null) {
            tmp = tmp.left;
        }
        // 递归删除节点 tmp
        remove(root, tmp.val);
        // 用 tmp 覆盖 cur
        cur.val = tmp.val;
    }
}
```

**二叉搜索树在中序遍历时，访问的元素是升序的。因此，我们可以利用二叉搜索树中序遍历升序的性质获取到第 k 大元素**

递归版本

```java
public class KthLargestInBST {

    private int count = 0;
    private int result = -1;

    public int kthLargest(TreeNode root, int k) {
        reverseInOrder(root, k);
        return result;
    }

    private void reverseInOrder(TreeNode node, int k) {
        if (node == null || count >= k) {
            return;
        }

        // 1. 先遍历右子树（大的）
        reverseInOrder(node.right, k);

        // 2. 访问当前节点
        count++;
        if (count == k) {
            result = node.val;
            return;
        }

        // 3. 再遍历左子树（小的）
        reverseInOrder(node.left, k);
    }
}
```

非递归版

```java
public int kthLargest(TreeNode root, int k) {
    Stack<TreeNode> stack = new Stack<>();
    TreeNode curr = root;

    while (curr != null || !stack.isEmpty()) {

        // 一直向右走
        while (curr != null) {
            stack.push(curr);
            curr = curr.right;
        }

        curr = stack.pop();
        k--;
        if (k == 0) {
            return curr.val;
        }

        curr = curr.left;
    }

    return -1; // k 不合法
}
```

