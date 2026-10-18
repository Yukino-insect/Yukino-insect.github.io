+++
date = '2025-08-07T10:28:27+08:00'
draft = false
title = '前端安全-XSS和CSRF'
+++

XSS 和 CSRF 都是 Web 安全里的高频概念，但它们攻击的点不同。

- XSS：让浏览器执行攻击者注入的脚本。
- CSRF：借用户已登录的身份，诱导浏览器发出非用户本意的请求。

一个是“把数据当代码执行”，一个是“把伪造请求当用户操作执行”。区别不大？当然大。把两者混在一起，面试官只需要安静地看你三秒。

## XSS

XSS 是跨站脚本攻击。攻击者把恶意脚本注入页面，浏览器渲染时执行了这些脚本，从而窃取 Cookie、Token、用户输入，或者篡改页面内容。

常见类型：

| 类型 | 说明 |
| --- | --- |
| 存储型 XSS | 恶意内容被保存到数据库，其他用户访问页面时触发 |
| 反射型 XSS | 恶意内容来自 URL 或请求参数，被服务端原样返回 |
| DOM 型 XSS | 前端脚本把不可信内容写入 DOM 并执行 |

典型危险写法：

```javascript
document.getElementById("content").innerHTML = userInput;
```

如果 `userInput` 是攻击者提交的脚本，就可能被浏览器执行。

### 防御方式

前端和后端都要做防御。

| 位置 | 措施 |
| --- | --- |
| 输入 | 校验格式，限制长度，过滤明显非法内容 |
| 输出 | 根据上下文做 HTML、URL、JavaScript 转义 |
| 前端渲染 | 避免直接使用 `innerHTML`，优先使用文本渲染 |
| Cookie | 设置 `HttpOnly`，降低脚本窃取风险 |
| 浏览器策略 | 配置 CSP，限制脚本来源 |

后端可以通过包装 `HttpServletRequest` 做统一过滤，但它不是万能方案。真正可靠的做法是：**输出到哪里，就按哪里的语法做转义**。

示例结构：

```java
public class XssFilter implements Filter {

    @Override
    public void doFilter(ServletRequest request,
                         ServletResponse response,
                         FilterChain chain)
            throws IOException, ServletException {
        chain.doFilter(new XssRequestWrapper((HttpServletRequest) request), response);
    }
}

public class XssRequestWrapper extends HttpServletRequestWrapper {

    public XssRequestWrapper(HttpServletRequest request) {
        super(request);
    }

    @Override
    public String getParameter(String name) {
        String value = super.getParameter(name);
        return escape(value);
    }
}
```

这种过滤适合处理一部分普通文本输入，但富文本、Markdown、代码片段等场景不能粗暴替换，否则会误伤合法内容。安全不是把所有尖括号都剪掉，那只是另一种懒。

## CSRF

CSRF 是跨站请求伪造。用户已经在 A 网站登录，攻击者诱导用户访问 B 网站，B 网站偷偷让浏览器向 A 网站发请求。因为浏览器会自动携带 A 网站的 Cookie，A 网站可能误以为这是用户主动操作。

典型场景：

```html
<form action="https://bank.example.com/transfer" method="post">
  <input name="to" value="attacker">
  <input name="amount" value="1000">
</form>
<script>
  document.forms[0].submit();
</script>
```

如果转账接口只依赖 Cookie 判断登录态，并且没有额外校验，就可能被伪造。

### 防御方式

| 措施 | 作用 |
| --- | --- |
| CSRF Token | 页面或接口携带不可预测 Token，服务端校验 |
| SameSite Cookie | 限制跨站请求自动携带 Cookie |
| 校验 Origin/Referer | 拒绝异常来源请求 |
| 重要操作二次确认 | 转账、改密、解绑等操作增加确认 |
| 避免 GET 修改数据 | GET 应该只读，不承担状态变更 |

如果前后端分离项目使用 `Authorization: Bearer token`，并且 Token 不放在 Cookie 里，CSRF 风险会降低，因为跨站表单和图片请求不能自动带上这个请求头。

但如果你把 JWT 放在 Cookie 里，让浏览器自动携带，那它依旧会面对 CSRF 问题。不要因为用了 JWT 就觉得自己从此高枕无忧，安全问题不会被名词感动。

## XSS 和 CSRF 的关系

XSS 往往比 CSRF 更危险。因为一旦攻击者能执行脚本，就可能直接读取页面内容、调用接口、获取 CSRF Token，再绕过部分 CSRF 防护。

所以优先级通常是：

```text
先防 XSS，再谈 CSRF。
```

当然，这不是说 CSRF 可以不管。只是如果页面已经允许执行任意脚本，CSRF Token 也会变得很脆弱。

## 小结

XSS 防的是脚本注入，重点是输入校验、输出转义、CSP 和避免危险 DOM 操作。CSRF 防的是伪造请求，重点是 CSRF Token、SameSite、Origin 校验和正确使用 HTTP 方法。两个问题都不复杂，复杂的是在真实项目里坚持不走捷径。
