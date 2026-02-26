# BTC Enhanced DCA

[中文说明](#chinese)

An intelligent Bitcoin Dollar Cost Averaging (DCA) tool that dynamically adjusts daily investment amounts based on the [Ahr999](https://github.com/CoxxA/bitcoin-ahr999-HODL) indicator.

## Features

- **Dynamic Investment Multiplier**: Automatically adjusts investment amounts based on market conditions (supports custom configuration, default 0.1x - 4.0x)
- **Smart Indicator**: Decision-making based on Ahr999
- **Automated Trading**: Executes BTC/USDT spot market buy orders via OKX API
- **GitHub Actions Integration**: No server needed, runs automatically daily and logs results to GitHub Issues
- **Investment Records**: Stores daily strategy snapshots in `docs/data/investment_records.csv`
- **Performance Dashboard**: Publishes strategy/benchmark PnL curves to GitHub Pages (`docs/`)

## Quick Start

### Prerequisites

[Register an OKX account](https://www.glneokotyjv.com/join/14514410) and [configure API](https://www.okx.com/account/my-api). After configuration, record your **API Key**, **Secret Key**, and **Passphrase**.

When creating the API, please check **Read** and **Trade** permissions. For security reasons, it is recommended not to check **Withdraw**.

### Run with GitHub Actions (Recommended)

No deployment or server needed, runs automatically every day and logs results to Issues.

1. **Fork this repository** to your GitHub account

2. **Clear historical record directories**

   After forking, delete historical data in `docs/data/` first. This avoids mixing the original repository's historical performance with your own records.

3. **Configure GitHub Secrets**

   Go to your repository: `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

   Add the following Secrets:

   **Required Secrets:**
   - `OKX_API_KEY` - Your OKX API Key
   - `OKX_SECRET_KEY` - Your OKX Secret Key
   - `OKX_PASSPHRASE` - Your OKX Passphrase

   **Optional Secrets:**
   
   - `BASE_INVESTMENT_AMOUNT` - Base DCA amount (USDT, default: 10.0)
   - `MIN_MULTIPLIER` - Minimum DCA multiplier (default: 0.1)
   - `MAX_MULTIPLIER` - Maximum DCA multiplier (default: 4.0)

4. **Enable GitHub Pages (one-time)**

   - Go to `Settings` -> `Pages`
   - Set Source to `Deploy from a branch`
   - Branch: `main`, Folder: `/docs`
   - Save, then open the published URL to view the performance dashboard
   
5. **Verify Workflow**

   - Go to the `Actions` tab of your repository
   - Click on the `Daily BTC Enhanced DCA` workflow
   - Click `Run workflow` → `Run workflow` to perform manual testing. Note that if execution succeeds, actual trading will occur
   - Check the workflow run logs to ensure no errors

6. **Automatic Execution**

   The workflow will run automatically every day. Each execution creates a GitHub Issue showing:
   - Current BTC price
   - Ahr999 indicator value
   - Investment amount
   - Execution status and logs
   - Portfolio snapshot (cumulative invest, value, PnL, benchmark comparison)

### Local Run

This project also supports local execution:

```powershell
# Clone repository
git clone <your-repo-url>
cd btc-enhanced-dca

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or create .env file)
set OKX_API_KEY=your_api_key
set OKX_SECRET_KEY=your_secret_key
set OKX_PASSPHRASE=your_passphrase

# Run script
python src/main.py
```

## How It Works

### 1. Data Collection
Fetch current BTC price and 200-day price history from OKX/Binance for Ahr999 calculation

### 2. Indicator Calculation

**Ahr999**

```
ahr999 = (Current Price / 200-day DCA Cost) * (Current Price / Exponential Growth Valuation)
```
- Ahr999 > 1.2: No investment (overvalued)
- 0.45 < Ahr999 < 1.2: Regular DCA
- Ahr999 < 0.45: Buy the dip
- Lower Ahr999 = Better value = More investment

### 3. Investment Decision

Investment multiplier calculation formula:
```
Multiplier = (Minimum Multiplier + k × (DCA Line - Ahr999)² / Ahr999)
```

- Final Investment Amount = Base Amount × Multiplier

- Range: 0.1 to 4.0 times base amount, configurable

- When Ahr999 > 1.2: No investment

- k value is calculated based on the set minimum DCA amount to ensure smooth curve

- Can be modified in [src/data/calculator.py](https://github.com/Eumenides-K/btc-enhanced-dca/blob/main/src/data/calculator.py)

  

### 4. Trade Execution

- Execute BTC/USDT spot market buy order on OKX
- Issue records execution details

## Risk Disclaimer

- This tool only performs buy operations, sell operations need to be executed manually
- This tool is for educational purposes only
- Cryptocurrency trading carries significant risks
- Past performance does not indicate future results
- Use at your own risk, only invest what you can afford to lose
- Ensure OKX API credentials have appropriate permissions and are stored securely

## License

MIT License

---

<a name="chinese"></a>
# BTC Enhanced DCA

一个智能的比特币定投工具，根据 [Ahr999](https://github.com/CoxxA/bitcoin-ahr999-HODL) 指标动态调整每日投资金额。

## 功能特点

- **动态投资倍数**：根据市场状况自动调整投资金额（支持自定义配置，默认0.1x - 4.0x）
- **智能指标**：基于 Ahr999 进行决策
- **自动交易**：通过 OKX API 执行 BTC/USDT 现货市价买入订单
- **GitHub Actions 集成**：无需服务器，每日自动运行并将结果记录到 GitHub Issues
- **投资记录**：将每日策略快照写入 `docs/data/investment_records.csv`
- **收益看板**：在 GitHub Pages 发布策略/基准收益曲线（`docs/`）

## 快速开始

### 前置要求

[注册 OKX 账户](https://www.glneokotyjv.com/join/14514410)并[配置 API](https://www.okx.com/account/my-api)，完成配置后，记录**API Key**、**Secret Key**和**Passphrase**。

创建API时，请勾取**读取**和**交易**权限，出于安全考量推荐不要勾选**提现**。


### 使用 GitHub Actions  运行（推荐）

无需部署或服务器，每天自动运行，并将结果记录到 Issues 中。

1. **Fork 本仓库** 到您的 GitHub 账户

2. **清理历史记录目录**

   Fork 后请先删除 `docs/data/` 中的历史数据，这样可以避免原仓库历史收益数据混入你自己的投资记录。

3. **配置 GitHub Secrets**

   进入您的仓库：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

   添加以下 Secrets：

   **必需的 Secrets：**
   - `OKX_API_KEY` - 您的 OKX API Key
   - `OKX_SECRET_KEY` - 您的 OKX Secret Key
   - `OKX_PASSPHRASE` - 您的 OKX Passphrase

   **可选的 Secrets**：
   
   - `BASE_INVESTMENT_AMOUNT` - 基础定投金额（USDT，默认：10.0）
   - `MIN_MULTIPLIER` - 最小定投倍率 （默认：0.1）
   - `MAX_MULTIPLIER` - 最大定投倍率 （默认：4.0）

4. **启用 GitHub Pages**

   - 进入 `Settings` → `Pages`
   - Source 选择 `Deploy from a branch`
   - Branch 选择 `main`，Folder 选择 `/docs`
   - 保存后访问发布地址查看收益看板
   
5. **验证工作流**

   - 进入仓库的 `Actions` 标签页
   - 点击 `Daily BTC Enhanced DCA` 工作流
   - 点击 `Run workflow` → `Run workflow` 进行手动测试，注意此时若执行成功会进行交易
   - 查看工作流运行日志，确认无错误

6. **自动执行**

   工作流将每天自动运行一次。每次执行都会创建一个 GitHub Issue，显示：
   - 当前 BTC 价格
   - Ahr999 指标值
   - 投资金额
   - 执行状态和日志
   - 组合快照（累计投入、组合价值、盈亏、基准对比）

### 本地运行

本项目也支持本地运行：

```powershell
# 克隆仓库
git clone <your-repo-url>
cd btc-enhanced-dca

# 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 设置环境变量（或创建 .env 文件）
set OKX_API_KEY=你的_api_key
set OKX_SECRET_KEY=你的_secret_key
set OKX_PASSPHRASE=你的_passphrase

# 运行脚本
python src/main.py
```

## 工作原理

### 1. 数据收集
从 OKX/Binance 获取当前 BTC 价格及 200 天价格历史用于 Ahr999 计算

### 2. 指标计算

**Ahr999**

```
ahr999 = (当前价格 / 200日定投成本) * (当前价格 / 指数增长估值)
```
- Ahr999 > 1.2：不投资（高估）
- 0.45 <  Ahr999 < 1.2：定投
- Ahr999 < 0.45：抄底
- Ahr999 越低 = 价值越好 = 投资越多

### 3. 投资决策

投资倍数计算公式：
```
倍数 = (最小倍数 + k × (定投线 - Ahr999)² / Ahr999)
```

- 最终投资金额 = 基础金额 × 倍数

- 范围：基础金额的 0.1 到 4.0 倍，支持配置

- 当 Ahr999 > 1.2 时：不投资

- k 值根据设定的最小定投金额计算，确保曲线平滑

- 可在 [src/data/calculator.py](https://github.com/Eumenides-K/btc-enhanced-dca/blob/main/src/data/calculator.py) 中修改

  

### 4. 交易执行

- 在 OKX 上执行 BTC/USDT 现货市价买入订单
- Issue 记录执行详情

## 风险提示

- 本工具只进行买入操作，若需卖出需要手动执行
- 本工具仅供教育目的使用
- 加密货币交易存在重大风险
- 过往表现不代表未来结果
- 使用风险自负，仅投资个人能承受的损失
- 确保 OKX API 凭证具有适当权限并妥善保管

## 许可证

本项目采用MIT许可证。
