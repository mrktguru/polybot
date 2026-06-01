# Polymarket Trading Bot — Стратегии: Спецификация разработки

## Обзор

Бот реализует 6 стратегий с разным уровнем автоматизации.
Каждая стратегия — отдельный модуль с единым интерфейсом.

```
app/strategies/
  ├── base.py                 # BaseStrategy (интерфейс)
  ├── market_making.py        # ✅ Fully Auto
  ├── cross_market_corr.py    # ✅ Fully Auto
  ├── resolution_arb.py       # ✅ Auto (при наличии data feed)
  ├── volatility_harvest.py   # ⚡ Semi-Auto
  ├── whale_copy.py           # ⚡ Semi-Auto
  └── sentiment_divergence.py # ⚡ Semi-Auto
```

---

## Базовый интерфейс стратегии

```python
# app/strategies/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class AutomationLevel(Enum):
    FULL  = "full"   # бот торгует сам
    SEMI  = "semi"   # бот предлагает, человек подтверждает
    HUMAN = "human"  # только информирование

class SignalDirection(Enum):
    BUY_YES = "buy_yes"
    BUY_NO  = "buy_no"
    CLOSE   = "close"
    HOLD    = "hold"

@dataclass
class Signal:
    strategy:       str
    market_id:      str
    market_title:   str
    direction:      SignalDirection
    confidence:     float           # 0.0–1.0
    edge:           float           # наш edge vs рынок
    kelly_size:     float           # $ размер позиции
    entry_price:    float
    reasoning:      str
    auto_execute:   bool            # True = исполнить без подтверждения
    expires_in_sec: int             # через сколько сигнал устаревает
    metadata:       dict            # специфичные данные стратегии

@dataclass
class StrategyResult:
    signals:        list[Signal]
    markets_scanned: int
    execution_time_ms: int
    errors:         list[str]

class BaseStrategy(ABC):
    automation_level: AutomationLevel
    name: str

    @abstractmethod
    def scan(self, markets: list[dict]) -> StrategyResult:
        """Основной метод — сканирует рынки, возвращает сигналы"""
        pass

    @abstractmethod
    def execute(self, signal: Signal) -> dict:
        """Исполняет конкретный сигнал"""
        pass

    def should_auto_execute(self, signal: Signal) -> bool:
        return (
            self.automation_level == AutomationLevel.FULL
            and signal.confidence >= self.min_confidence
            and signal.kelly_size <= self.max_auto_size
        )
```

---

## Стратегия 1: Market Making

**Автоматизация: 100% | Основной доход**

### Параметры (настраиваются в Settings UI)

```python
@dataclass
class MMConfig:
    # Алгоритм котирования
    gamma:              float = 0.10    # риск-параметр (0.01–0.5)
    kappa:              float = 1.50    # глубина рынка (0.5–5.0)
    q_max:              float = 50.0    # макс инвентарь в токенах

    # Отбор рынков
    min_spread:         float = 0.03    # минимальный спред для входа
    min_volume_day:     float = 500.0   # мин объём $
    max_volume_day:     float = 8000.0  # макс объём $
    min_days:           int   = 7       # мин дней до резолюции
    max_days:           int   = 90      # макс дней до резолюции
    min_score:          float = 0.45    # порог MarketSelector
    max_active_markets: int   = 12      # рынков одновременно

    # Риск
    max_position_usd:   float = 25.0    # макс $ на рынок
    kill_zone_hours:    int   = 48      # часов до резолюции → снять всё
    max_price_jump_1h:  float = 0.10    # spike → пауза MM

    # Excluded категории
    excluded_categories: list = field(default_factory=lambda: [
        "crypto_price_short",
        "breaking_news",
        "sports_live",
    ])
```

### Жизненный цикл

```
Celery beat каждый час:
  refresh_market_selection()
    → Gamma API: все активные рынки
    → hard_filter() → ~200 рынков
    → MarketSelector.score() → топ-30
    → LLM curator (Haiku) → keywords, flags
    → сохранить в Redis "active_mm_markets"

Celery beat каждые 60 секунд:
  mm_quote_update()
    → читать active_mm_markets из Redis
    → для каждого рынка:
        orderbook = clob.get_orderbook()
        quotes = InventorySkewMM.compute_quotes()
        if quotes changed > 0.5¢:
            clob.cancel_all(market)
            clob.place_limit(bid)
            clob.place_limit(ask)

Celery worker (event):
  on_fill(order_id, price, size)
    → обновить inventory в PostgreSQL
    → пересчитать quotes немедленно
    → WebSocket push → UI
```

### Алгоритм котирования (InventorySkewMM)

```python
def compute_quotes(mid, q, sigma, T_hours) -> dict:

    if T_hours < kill_zone_hours or abs(q) >= q_max:
        return {"action": "cancel_all"}

    T = T_hours / 24

    # Reservation price — сдвигается при накоплении инвентаря
    r = mid - q * gamma * (sigma ** 2) * T

    # Оптимальный спред
    import numpy as np
    delta = gamma * (sigma ** 2) * T + (2 / gamma) * np.log(1 + gamma / kappa)

    bid = max(0.01, min(r - delta / 2, 0.98))
    ask = max(0.02, min(r + delta / 2, 0.99))

    if ask <= bid:
        ask = bid + 0.02

    return {
        "bid": round(bid, 3),
        "ask": round(ask, 3),
        "spread": round(ask - bid, 3),
        "action": "quote",
    }
```

### MarketSelector — scoring

```python
def score(market) -> float:
    spread = market.best_ask - market.best_bid

    # Hard filters — return None немедленно
    if spread < config.min_spread:      return None
    if T_hours < config.kill_zone_hours: return None

    # Компоненты score
    spread_score = min(spread / 0.15, 1.0)

    v = market.volume_24h
    if v < 200:       liq_score = 0.0
    elif v < 500:     liq_score = v / 500 * 0.4
    elif v <= 8000:   liq_score = 0.4 + (v - 500) / 7500 * 0.6
    else:             liq_score = max(0, 1.0 - (v - 8000) / 20000)

    T = T_hours / 24
    if T < 7:         time_score = (T - 2) / 5 * 0.5
    elif T <= 30:     time_score = 1.0
    elif T <= 90:     time_score = 1.0 - (T - 30) / 60 * 0.4
    else:             time_score = 0.6

    sigma = compute_sigma(market.price_history)
    if sigma < 0.01:    vol_score = 0.2
    elif sigma <= 0.05: vol_score = 1.0
    elif sigma <= 0.12: vol_score = 1.0 - (sigma - 0.05) / 0.07 * 0.6
    else:               vol_score = 0.0

    # Penalties
    penalty = 0.0
    if market.mid < 0.05 or market.mid > 0.95: penalty += 0.4
    if market.max_jump_1h > 0.10:               penalty += 0.3
    if market.orderbook_depth < 3:              penalty += 0.2
    if market.category in excluded_categories:  penalty += 0.25

    raw = 0.35*spread_score + 0.25*liq_score + 0.20*time_score + 0.20*vol_score
    return max(0.0, raw - penalty)
```

### База данных

```sql
-- Активные MM позиции
CREATE TABLE mm_positions (
    market_id       TEXT PRIMARY KEY,
    inventory       FLOAT DEFAULT 0,
    current_bid     FLOAT,
    current_ask     FLOAT,
    total_bought    FLOAT DEFAULT 0,
    total_sold      FLOAT DEFAULT 0,
    realized_pnl    FLOAT DEFAULT 0,
    score           FLOAT,
    added_at        TIMESTAMPTZ DEFAULT NOW(),
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

-- История всех ордеров
CREATE TABLE mm_orders (
    order_id        TEXT PRIMARY KEY,
    market_id       TEXT REFERENCES mm_positions,
    side            TEXT,      -- buy | sell
    price           FLOAT,
    size            FLOAT,
    status          TEXT,      -- open | filled | cancelled
    fill_price      FLOAT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    filled_at       TIMESTAMPTZ
);

-- Снапшоты цен для расчёта sigma
CREATE TABLE price_snapshots (
    id          BIGSERIAL PRIMARY KEY,
    market_id   TEXT,
    mid_price   FLOAT,
    ts          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON price_snapshots (market_id, ts DESC);
```

---

## Стратегия 2: Cross-Market Correlation

**Автоматизация: 90% | Арбитраж логических связей**

### Типы связей которые ищет бот

```python
RELATION_TYPES = {

    # Вложенные события (nested)
    # P(к дате A) <= P(к дате B) если A < B
    "nested_dates": {
        "example": ["IPO OpenAI к июню", "IPO OpenAI к сентябрю"],
        "rule": "earlier_prob <= later_prob",
        "violation_threshold": 0.05,  # нарушение > 5%
    },

    # Взаимоисключающие + полные (exhaustive)
    # сумма вероятностей = 1.0
    "exhaustive": {
        "example": ["осадки <350мм", "350-375мм", "375-400мм", ...],
        "rule": "sum(all) == 1.0",
        "violation_threshold": 0.08,
    },

    # Условные (conditional)
    # P(A и B) <= P(A)
    "conditional": {
        "example": ["ФРС снизит в июле", "ФРС снизит в 2026"],
        "rule": "specific_prob <= general_prob",
        "violation_threshold": 0.05,
    },

    # Implied вероятности
    # P(событие в периоде) = P(к концу) - P(к началу)
    "implied_period": {
        "example": "IPO именно в сентябре = P(к сент) - P(к авг)",
        "rule": "implied >= 0 AND implied <= reasonable_max",
    },
}
```

### Алгоритм обнаружения

```python
class CrossMarketCorrelation(BaseStrategy):
    automation_level = AutomationLevel.FULL

    def scan(self, markets):
        signals = []

        # 1. LLM строит граф связей (раз в час)
        #    "Какие из этих 30 рынков логически связаны?"
        relations = self.llm_build_graph(markets)

        # 2. Для каждой пары/группы проверяем нарушение
        for relation in relations:
            violation = self.check_violation(relation)

            if violation and violation.magnitude > threshold:
                # 3. Рассчитываем позицию
                signal = self.build_signal(relation, violation)
                signals.append(signal)

        return StrategyResult(signals=signals, ...)

    def check_violation(self, relation) -> Optional[Violation]:
        if relation.type == "nested_dates":
            # P(к июню) = 1%, P(к сентябрю) = 44%
            # implied сентябрь = 43%  ← это и есть торгуемое
            for i in range(len(relation.markets) - 1):
                p_early = relation.markets[i].mid
                p_late  = relation.markets[i+1].mid
                implied = p_late - p_early

                if implied > self.config.max_implied_single_period:
                    return Violation(
                        type="implied_too_high",
                        magnitude=implied - expected,
                        trade_market=relation.markets[i+1],
                        direction="NO",
                    )
        ...

    def build_signal(self, relation, violation) -> Signal:
        # Kelly на основе magnitude нарушения
        edge = violation.magnitude
        p_correct = 0.5 + edge  # консервативная оценка
        kelly = compute_kelly(p_correct, entry_price)

        return Signal(
            strategy="cross_market_correlation",
            market_id=violation.trade_market.id,
            direction=SignalDirection.BUY_NO if violation.direction == "NO"
                      else SignalDirection.BUY_YES,
            confidence=min(edge * 3, 0.9),  # calibrated
            edge=edge,
            kelly_size=kelly,
            auto_execute=True,  # полная автоматизация
            reasoning=f"Implied {violation.type}: {edge:.1%} аномалия",
            expires_in_sec=3600,
            metadata={"relation": relation, "violation": violation},
        )
```

### Одобрение пар рынков человеком

```
При первом обнаружении связи между двумя рынками:
  → бот НЕ торгует автоматически
  → создаёт задачу в UI: "Проверь Rules этих двух рынков"
  → пользователь смотрит Rules → нажимает [Approve]
  → пара сохраняется в approved_pairs таблице
  → все будущие нарушения этой пары → авто-торговля

Повторное одобрение не нужно.
```

```sql
CREATE TABLE approved_market_pairs (
    id              BIGSERIAL PRIMARY KEY,
    market_id_a     TEXT,
    market_id_b     TEXT,
    relation_type   TEXT,
    approved_at     TIMESTAMPTZ,
    approved_by     TEXT DEFAULT 'user',
    notes           TEXT
);
```

---

## Стратегия 3: Resolution Arbitrage

**Автоматизация: 80% | Требует прямого data feed**

### Data feeds по категориям

```python
DATA_FEEDS = {
    "fed_rates": {
        "url": "https://www.federalreserve.gov/releases/h15/",
        "parser": "FedRatesParser",
        "poll_interval_sec": 60,
        "keywords": ["federal funds rate", "fomc decision"],
    },
    "cdc_health": {
        "url": "https://data.cdc.gov/api/...",
        "parser": "CDCParser",
        "poll_interval_sec": 300,
        "keywords": ["confirmed case", "outbreak"],
    },
    "crypto_prices": {
        "url": "wss://stream.binance.com/ws",
        "parser": "BinancePriceParser",
        "poll_interval_sec": 1,
        "keywords": ["BTC", "ETH", "XRP"],
    },
    "sec_filings": {
        "url": "https://efts.sec.gov/LATEST/search-index?",
        "parser": "SECParser",
        "poll_interval_sec": 120,
        "keywords": ["S-1", "IPO", "initial public offering"],
    },
}
```

### Логика исполнения

```python
class ResolutionArbitrage(BaseStrategy):

    def on_data_update(self, feed_name, data):
        """Вызывается при обновлении любого feed"""

        # Найти рынки связанные с этим feed
        related = db.get_markets_by_feed(feed_name)

        for market in related:
            outcome = self.determine_outcome(market, data)

            if outcome is not None:   # исход определён
                current_price = clob.get_mid(market.id)

                # Если рынок ещё не отражает исход
                if outcome == "YES" and current_price < 0.97:
                    gap = 1.0 - current_price
                    if gap > self.config.min_arb_gap:  # > 3¢
                        self.execute_immediately(
                            market_id=market.id,
                            direction="YES",
                            size=self.config.arb_position_size,
                        )

                elif outcome == "NO" and current_price > 0.03:
                    gap = current_price - 0.0
                    if gap > self.config.min_arb_gap:
                        self.execute_immediately(
                            market_id=market.id,
                            direction="NO",
                            size=self.config.arb_position_size,
                        )
```

---

## Стратегия 4: Volatility Harvesting

**Автоматизация: 75% | Триггер авто, вход — подтверждение**

### Детектор spike

```python
class VolatilityHarvesting(BaseStrategy):
    automation_level = AutomationLevel.SEMI

    # Параметры
    spike_threshold:    float = 0.08   # 8% за 30 минут = триггер
    min_uncertainty:    float = 0.25   # mid должен быть 0.25–0.75
    max_uncertainty:    float = 0.75
    contrarian_target:  float = 0.60   # откат к этой точке = выход
    stop_loss_pct:      float = 0.05   # стоп если продолжает идти

    def detect_spike(self, market_id) -> Optional[SpikeEvent]:
        # Последние 2 снапшота (30 минут)
        snapshots = db.get_snapshots(market_id, limit=2)
        if len(snapshots) < 2:
            return None

        price_change = abs(snapshots[0].mid - snapshots[1].mid)

        if price_change < self.spike_threshold:
            return None

        # Проверить: есть ли реальная новость?
        recent_news = db.get_news_for_market(market_id, minutes=35)
        news_confirmed = self.llm_check_real_news(market_id, recent_news)

        if news_confirmed:
            return None  # реальная новость, не overshooting

        direction = "DOWN" if snapshots[0].mid > snapshots[1].mid else "UP"

        return SpikeEvent(
            market_id=market_id,
            spike_direction=direction,
            magnitude=price_change,
            current_price=snapshots[0].mid,
            contrarian_side="NO" if direction == "UP" else "YES",
        )

    def build_signal(self, spike: SpikeEvent) -> Signal:
        # Контрарная позиция — ставим против движения
        entry = (spike.current_price
                 if spike.contrarian_side == "YES"
                 else 1 - spike.current_price)

        return Signal(
            strategy="volatility_harvesting",
            market_id=spike.market_id,
            direction=(SignalDirection.BUY_YES
                       if spike.contrarian_side == "YES"
                       else SignalDirection.BUY_NO),
            confidence=min(spike.magnitude * 5, 0.80),
            edge=spike.magnitude * 0.6,  # ожидаем 60% откат
            kelly_size=50.0,             # фиксированный размер VH
            entry_price=entry,
            auto_execute=False,          # ждём подтверждения
            reasoning=(f"Spike {spike.magnitude:.1%} без подтверждённой "
                       f"новости → вероятный overshooting"),
            expires_in_sec=300,          # сигнал устаревает за 5 минут
            metadata={"spike": spike},
        )

    def monitor_open_positions(self):
        """Управление открытыми VH позициями"""
        for pos in db.get_open_vh_positions():
            current = clob.get_mid(pos.market_id)

            # Целевой выход — откат состоялся
            if pos.side == "NO":
                no_price = 1 - current
                if no_price >= pos.entry_price * 1.20:  # +20%
                    self.close_position(pos, reason="target_reached")

            # Стоп-лосс — движение продолжилось
            if pos.side == "NO":
                no_price = 1 - current
                if no_price < pos.entry_price * (1 - self.stop_loss_pct):
                    self.close_position(pos, reason="stop_loss")
```

---

## Стратегия 5: Whale Copying

**Автоматизация: 60% | Мониторинг авто, копирование — кнопка**

### Мониторинг ончейн активности

```python
class WhaleCopying(BaseStrategy):
    automation_level = AutomationLevel.SEMI

    # Параметры
    min_bet_usd:            float = 5000    # мин размер "whale" ставки
    new_wallet_tx_limit:    int   = 5       # кошелёк считается новым
    percentile_threshold:   float = 0.95    # топ 5% по размеру
    copy_delay_sec:         int   = 30      # задержка перед копированием
    copy_size_pct:          float = 0.10    # копируем 10% от whale ставки

    def monitor_transactions(self):
        """
        Читаем Polygon транзакции через The Graph subgraph
        или напрямую через RPC
        """
        # GraphQL запрос к Polymarket subgraph
        query = """
        {
          positionTrades(
            first: 100,
            orderBy: timestamp,
            orderDirection: desc,
            where: { timestamp_gte: $last_check }
          ) {
            trader { id }
            market { id question }
            side
            amount
            price
            timestamp
          }
        }
        """
        trades = graphql.query(POLYMARKET_SUBGRAPH, query)

        for trade in trades:
            self.analyze_trade(trade)

    def analyze_trade(self, trade):
        usd_value = trade.amount * trade.price

        # Фильтр по размеру
        if usd_value < self.min_bet_usd:
            return

        wallet = trade.trader.id
        wallet_history = db.get_wallet_history(wallet)

        # Считаем метрики кошелька
        metrics = {
            "total_bets":    len(wallet_history),
            "win_rate":      self.calc_win_rate(wallet_history),
            "calibration":   self.calc_calibration(wallet_history),
            "is_new_wallet": len(wallet_history) < self.new_wallet_tx_limit,
            "bet_percentile": self.calc_percentile(usd_value, trade.market.id),
        }

        # Флаги подозрительности
        is_whale = (
            usd_value >= self.min_bet_usd
            and metrics["bet_percentile"] >= self.percentile_threshold
        )

        is_smart = (
            metrics["win_rate"] > 0.60
            and metrics["calibration"] > 0.65
            and metrics["total_bets"] >= 20
        )

        if is_whale:
            self.create_whale_alert(trade, metrics, is_smart)

    def create_whale_alert(self, trade, metrics, is_smart):
        alert = WhaleAlert(
            wallet=trade.trader.id,
            market_id=trade.market.id,
            market_title=trade.market.question,
            side=trade.side,
            usd_value=trade.amount * trade.price,
            metrics=metrics,
            is_smart_money=is_smart,
            copy_size=trade.amount * trade.price * self.copy_size_pct,
        )

        db.save_whale_alert(alert)
        websocket.broadcast("whale.alert", alert)

        # Push уведомление пользователю
        telegram.send(
            f"🐋 WHALE ALERT\n"
            f"Рынок: {trade.market.question}\n"
            f"Сторона: {trade.side}\n"
            f"Размер: ${alert.usd_value:,.0f}\n"
            f"Кошелёк win rate: {metrics['win_rate']:.0%}\n"
            f"Smart money: {'✅' if is_smart else '❓'}\n"
            f"Предлагаемая копия: ${alert.copy_size:.0f}"
        )
        # Пользователь нажимает [Copy] в дашборде
```

### Рейтинг кошельков

```sql
-- Таблица отслеживаемых кошельков
CREATE TABLE tracked_wallets (
    address         TEXT PRIMARY KEY,
    total_bets      INT DEFAULT 0,
    wins            INT DEFAULT 0,
    total_wagered   FLOAT DEFAULT 0,
    total_profit    FLOAT DEFAULT 0,
    win_rate        FLOAT GENERATED ALWAYS AS (wins::float / NULLIF(total_bets, 0)) STORED,
    calibration     FLOAT,  -- считается отдельно
    last_bet_at     TIMESTAMPTZ,
    is_watchlisted  BOOL DEFAULT FALSE,
    notes           TEXT
);

-- История ставок по кошелькам
CREATE TABLE wallet_bets (
    id              BIGSERIAL PRIMARY KEY,
    wallet_address  TEXT REFERENCES tracked_wallets,
    market_id       TEXT,
    side            TEXT,
    amount_usd      FLOAT,
    entry_price     FLOAT,
    outcome         TEXT,    -- win | loss | pending
    profit_usd      FLOAT,
    bet_at          TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ
);
```

---

## Стратегия 6: Sentiment Divergence

**Автоматизация: 50% | Сравнение авто, решение — человек**

### Источники для сравнения

```python
COMPARISON_SOURCES = {
    "metaculus": {
        "api_url":      "https://www.metaculus.com/api2/questions/",
        "poll_interval": 900,  # 15 минут
        "reliability":  0.75,
    },
    "predictit": {
        "api_url":      "https://www.predictit.org/api/marketdata/all/",
        "poll_interval": 300,
        "reliability":  0.80,
    },
    "manifold": {
        "api_url":      "https://manifold.markets/api/v0/markets",
        "poll_interval": 600,
        "reliability":  0.60,
    },
    "betting_odds": {
        "api_url":      "https://api.the-odds-api.com/v4/sports/",
        "poll_interval": 300,
        "reliability":  0.85,
        "categories":  ["sports"],
    },
}
```

### Алгоритм поиска divergence

```python
class SentimentDivergence(BaseStrategy):
    automation_level = AutomationLevel.SEMI

    min_gap:        float = 0.08    # минимальный gap для сигнала
    min_sources:    int   = 2       # минимум источников для подтверждения

    def find_divergences(self, polymarket_markets):
        signals = []

        for pm_market in polymarket_markets:
            # Найти соответствующий рынок на других платформах
            matches = self.find_matching_markets(pm_market)

            if len(matches) < self.min_sources:
                continue

            # Средневзвешенная вероятность по внешним источникам
            external_prob = self.weighted_average(matches)
            polymarket_prob = pm_market.mid

            gap = external_prob - polymarket_prob

            if abs(gap) < self.min_gap:
                continue

            # LLM: объяснить почему gap существует
            explanation = self.llm_explain_gap(
                pm_market, matches, gap
            )

            # Если объяснение = "аудиторный bias" → торговый сигнал
            # Если объяснение = "разные Rules" → пропустить
            if explanation.is_tradeable:
                signal = Signal(
                    strategy="sentiment_divergence",
                    market_id=pm_market.id,
                    direction=(SignalDirection.BUY_YES if gap > 0
                               else SignalDirection.BUY_NO),
                    confidence=explanation.confidence,
                    edge=abs(gap),
                    kelly_size=compute_kelly(
                        p=0.5 + abs(gap) * 0.5,
                        b=(1 - pm_market.mid) / pm_market.mid,
                        capital=self.config.directional_budget,
                    ),
                    auto_execute=False,  # всегда ждём человека
                    reasoning=explanation.summary,
                    expires_in_sec=7200,
                    metadata={
                        "polymarket_prob": polymarket_prob,
                        "external_prob":   external_prob,
                        "sources":         matches,
                        "gap":             gap,
                    },
                )
                signals.append(signal)

        return StrategyResult(signals=signals, ...)

    def llm_explain_gap(self, market, matches, gap) -> Explanation:
        prompt = f"""
Рынок Polymarket: "{market.title}"
Цена Polymarket: {market.mid:.2f}

Внешние оценки:
{chr(10).join(f"- {m.source}: {m.prob:.2f}" for m in matches)}

Gap: {gap:+.2f} (внешние {'выше' if gap > 0 else 'ниже'})

Объясни gap. Варианты:
1. Аудиторный bias Polymarket (крипто-аудитория, политические взгляды)
2. Разные Rules/определения события
3. Разные временные горизонты
4. Информационное преимущество одной из платформ
5. Временная неэффективность

Ответь JSON: {{
  "reason": "...",
  "is_tradeable": true/false,
  "confidence": 0.0-1.0,
  "summary": "одна фраза"
}}
"""
        return llm.query(prompt, model="claude-haiku")
```

---

## Общий менеджер стратегий

```python
# app/strategies/manager.py

class StrategyManager:
    """
    Оркестрирует все стратегии.
    Управляет капиталом между ними.
    """

    def __init__(self, total_capital: float):
        self.capital = total_capital
        self.budgets = {
            "market_making":         total_capital * 0.60,
            "cross_market_corr":     total_capital * 0.10,
            "resolution_arb":        total_capital * 0.05,
            "volatility_harvesting": total_capital * 0.10,
            "whale_copying":         total_capital * 0.05,
            "sentiment_divergence":  total_capital * 0.05,
            "reserve":               total_capital * 0.05,
        }

        self.strategies = {
            "market_making":         MarketMaking(self.budgets["market_making"]),
            "cross_market_corr":     CrossMarketCorrelation(...),
            "resolution_arb":        ResolutionArbitrage(...),
            "volatility_harvesting": VolatilityHarvesting(...),
            "whale_copying":         WhaleCopying(...),
            "sentiment_divergence":  SentimentDivergence(...),
        }

    def process_signal(self, signal: Signal) -> None:
        strategy = self.strategies[signal.strategy]

        if strategy.should_auto_execute(signal):
            # Полная автоматизация
            self.execute(signal)
        else:
            # Полуавтомат — сохранить для UI
            db.save_pending_signal(signal)
            websocket.broadcast("signal.new", signal)
            if signal.confidence > 0.70:
                telegram.notify(signal)

    def execute(self, signal: Signal) -> None:
        budget = self.budgets[signal.strategy]
        size = min(signal.kelly_size, budget * 0.20)  # не больше 20% бюджета

        if signal.direction in (SignalDirection.BUY_YES, SignalDirection.BUY_NO):
            clob.place_market_order(
                market_id=signal.market_id,
                side=signal.direction.value,
                size=size,
            )

        db.log_execution(signal, size)

    def check_circuit_breakers(self) -> None:
        """Вызывается каждую минуту"""
        daily_pnl = db.get_daily_pnl()

        if daily_pnl < -self.config.daily_loss_limit:
            self.pause_all(reason="daily_loss_limit")
            telegram.alert("🚨 DAILY LOSS LIMIT — все стратегии на паузе")

        drawdown = self.calc_drawdown()
        if drawdown > self.config.max_drawdown_pct:
            self.pause_all(reason="max_drawdown")
            telegram.alert(f"🚨 DRAWDOWN {drawdown:.1%} — все стратегии на паузе")
```

---

## Расписание Celery tasks

```python
# app/celery_config.py

CELERYBEAT_SCHEDULE = {
    # Market Making
    "mm-quote-update": {
        "task": "tasks.mm_quote_update",
        "schedule": 60.0,  # каждую минуту
    },
    "mm-market-refresh": {
        "task": "tasks.mm_market_refresh",
        "schedule": 3600.0,  # раз в час
    },
    "mm-price-snapshot": {
        "task": "tasks.price_snapshot",
        "schedule": 1800.0,  # каждые 30 минут
    },

    # Cross-Market Correlation
    "corr-scan": {
        "task": "tasks.correlation_scan",
        "schedule": 3600.0,
    },

    # Resolution Arbitrage
    "res-arb-poll": {
        "task": "tasks.resolution_arb_poll",
        "schedule": 60.0,
    },

    # Volatility Harvesting
    "vh-spike-detect": {
        "task": "tasks.vh_spike_detect",
        "schedule": 30.0,
    },
    "vh-position-monitor": {
        "task": "tasks.vh_position_monitor",
        "schedule": 60.0,
    },

    # Whale Copying
    "whale-monitor": {
        "task": "tasks.whale_monitor",
        "schedule": 30.0,
    },

    # Sentiment Divergence
    "sentiment-scan": {
        "task": "tasks.sentiment_scan",
        "schedule": 900.0,  # каждые 15 минут
    },

    # Общее
    "circuit-breakers": {
        "task": "tasks.check_circuit_breakers",
        "schedule": 60.0,
    },
    "daily-report": {
        "task": "tasks.daily_report",
        "schedule": crontab(hour=0, minute=0),
    },
}
```

---

## Порядок разработки

### Фаза 1 — Core (2–3 недели)
```
□ BaseStrategy интерфейс
□ StrategyManager скелет
□ MarketMaking полностью
  □ MarketSelector scoring
  □ InventorySkewMM котирование
  □ CLOB API интеграция
  □ Kill switch
  □ Paper trading mode
□ Circuit breakers
□ Базовые Celery tasks
□ PostgreSQL схема
□ Telegram уведомления
```

### Фаза 2 — Semi-Auto (1–2 недели)
```
□ VolatilityHarvesting
  □ Spike detector
  □ LLM проверка новости
  □ Signal → UI
□ WhaleCopying
  □ The Graph интеграция
  □ Wallet metrics
  □ Alert система
□ Signal queue в PostgreSQL
□ WebSocket для UI
```

### Фаза 3 — Analytics (2 недели)
```
□ CrossMarketCorrelation
  □ LLM граф связей
  □ Violation detector
  □ Approved pairs система
□ SentimentDivergence
  □ Metaculus API
  □ PredictIt API
  □ LLM объяснение gap
□ ResolutionArbitrage
  □ Data feeds (CDC, ФРС, SEC)
  □ Feed parsers
```

### Фаза 4 — Polish (1 неделя)
```
□ Backtesting runner
□ Strategy performance dashboard
□ Parameter optimization
□ Export / reporting
```

---

## Переменные окружения

```env
# Polymarket
POLYGON_PRIVATE_KEY=0x...
CLOB_API_KEY=...
CLOB_API_SECRET=...
CLOB_API_PASSPHRASE=...

# LLM
ANTHROPIC_API_KEY=...
LLM_CURATOR_MODEL=claude-haiku-4-5-20251001
LLM_ANALYSIS_MODEL=claude-sonnet-4-6

# Infrastructure
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0

# Notifications
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# External APIs
METACULUS_API_KEY=...
THE_ODDS_API_KEY=...

# Trading params
PAPER_TRADING=true
TOTAL_CAPITAL=500
DAILY_LOSS_LIMIT=50
MAX_DRAWDOWN_PCT=0.15
```
