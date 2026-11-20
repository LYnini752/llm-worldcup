# LLM 世界杯 · complete

- 比赛 ID: `synthetic-demo-0001`
- 报告版本: schema v1
- 生成时间: 2026-11-19T12:00:00+00:00
- 冠军: **Alpha**
- 随机种子（仅控制对阵）: 42

## 问题

怎样向初学者解释过拟合？请举一个具体例子。

## 评分维度

{"correctness": 40, "relevance": 25, "completeness": 20, "clarity": 15}

## 第 1 轮

### Alpha × Beta

**Alpha 的答案**

过拟合就像学生把往年考题答案背下来，遇到新题却不会举一反三。模型训练时把训练数据的噪声也记住了，训练集表现很好，新数据上反而变差。  _(1.42s · 61 tokens)_

**Beta 的答案**

过拟合指模型过于贴合训练数据，泛化能力下降。  _(0.83s · 18 tokens)_

- 晋级: **Alpha**

- 复评顺序 Alpha / Beta：判决 A，比分 84 : 62，耗时 0.41s
  - 理由：Alpha 有定义也有例子，更完整清晰。
- 复评顺序 Beta / Alpha：判决 B，比分 63 : 85，耗时 0.39s
  - 理由：换序后仍认为 Alpha 解释更充分。

### Gamma × Delta

**Gamma 的答案**

当模型复杂度太高、数据太少时，会记住随机波动而非规律。比如用高次曲线拟合少量散点，曲线来回穿过每个点，却无法预测新点。  _(1.17s · 55 tokens)_

**Delta 的答案**

过拟合。  _(0.21s · 3 tokens)_

- 晋级: **Gamma**

- 复评顺序 Gamma / Delta：判决 A，比分 80 : 20，耗时 0.37s
  - 理由：Gamma 给出机制和具体类比，Delta 几乎没有内容。
- 复评顺序 Delta / Gamma：判决 B，比分 22 : 81，耗时 0.4s
  - 理由：换序后结论不变，Gamma 明显更好。

## 第 2 轮

### Alpha × Gamma

**Alpha 的答案**

过拟合就像学生把往年考题答案背下来，遇到新题却不会举一反三。模型训练时把训练数据的噪声也记住了，训练集表现很好，新数据上反而变差。  _(1.42s · 61 tokens)_

**Gamma 的答案**

当模型复杂度太高、数据太少时，会记住随机波动而非规律。比如用高次曲线拟合少量散点，曲线来回穿过每个点，却无法预测新点。  _(1.17s · 55 tokens)_

- 晋级: **Alpha**

- 复评顺序 Alpha / Gamma：判决 A，比分 83 : 79，耗时 0.44s
  - 理由：两者都清楚，Alpha 的学生类比更贴近初学者。
- 复评顺序 Gamma / Alpha：判决 B，比分 78 : 82，耗时 0.42s
  - 理由：换序后 Alpha 的表达仍更易懂。

---

> 说明：Single-question bracket preference, not an overall model ranking. Seed only controls bracket; model outputs may vary.
