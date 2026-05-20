"""数据插值填充服务

为时序预测模型提供数据预处理，解决数据稀疏和缺失问题。

主要功能：
1. 时间序列重采样与插值填充
2. 数据密度评估
3. 预测粒度自适应选择（小时级 -> 日级降级）
4. 异常值处理

使用场景：
- AI 诊断报告生成前的数据预处理
- Prophet 时序预测前的数据标准化
- 小时级统计数据缺失时的填充
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from enum import Enum
import re
from typing import Any, Optional

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


class PredictionGranularity(str, Enum):
    """预测粒度枚举"""
    MINUTE_15 = "15min"     # 15分钟级（高精度）
    HOURLY = "hourly"       # 小时级（标准）
    DAILY = "daily"         # 日级（降级）


@dataclass
class DataQualityMetrics:
    """数据质量评估指标"""
    total_expected_points: int      # 期望的数据点数
    actual_points: int              # 实际数据点数
    coverage_rate: float            # 覆盖率 (0-1)
    missing_hours: list[int]        # 缺失的小时列表
    data_gaps: list[tuple[datetime, datetime]]  # 数据断档时段
    recommended_granularity: PredictionGranularity  # 推荐预测粒度
    interpolation_needed: bool      # 是否需要插值
    quality_score: float            # 综合质量评分 (0-100)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_expected_points": self.total_expected_points,
            "actual_points": self.actual_points,
            "coverage_rate": round(self.coverage_rate, 4),
            "missing_hours": self.missing_hours,
            "data_gaps_count": len(self.data_gaps),
            "recommended_granularity": self.recommended_granularity.value,
            "interpolation_needed": self.interpolation_needed,
            "quality_score": round(self.quality_score, 2),
        }


class DataInterpolator:
    """数据插值填充器

    支持多种插值策略：
    - linear: 线性插值（默认，适合平稳数据）
    - time: 基于时间的线性插值
    - pad/ffill: 前向填充（适合阶跃变化）
    - nearest: 最近邻插值
    - spline: 样条插值（适合平滑曲线）
    """

    # 数据质量阈值配置
    HOURLY_MIN_COVERAGE = 0.6       # 小时级预测最低覆盖率要求
    DAILY_MIN_COVERAGE = 0.3        # 日级预测最低覆盖率要求
    MIN_POINTS_PER_HOUR = 2         # 每小时最少需要的数据点数
    MAX_GAP_MINUTES = 120           # 最大允许插值的缺失时长（分钟）

    def __init__(
        self,
        target_interval: str = "5min",
        interpolation_method: str = "linear",
        max_interpolation_gap: int = 120,
    ):
        """
        初始化插值器。

        Args:
            target_interval: 目标采样间隔（如 "1min", "5min", "15min", "1h"）
            interpolation_method: 插值方法 (linear/time/pad/nearest/spline)
            max_interpolation_gap: 最大允许插值的时间间隔（分钟），超过则不插值
        """
        self.target_interval = self._normalize_frequency(target_interval)
        self.interpolation_method = interpolation_method
        self.max_interpolation_gap = max_interpolation_gap

    @staticmethod
    def _normalize_frequency(freq: str) -> str:
        """兼容 Pandas 新版本中已弃用的大写频率别名。"""
        normalized = freq.strip()
        match = re.fullmatch(r"(?P<count>\d+)?(?P<unit>[A-Za-z]+)", normalized)
        if not match:
            return normalized

        deprecated_aliases = {
            "H": "h",
            "T": "min",
            "S": "s",
            "L": "ms",
            "U": "us",
            "N": "ns",
        }
        count = match.group("count") or ""
        unit = match.group("unit")
        return f"{count}{deprecated_aliases.get(unit, unit)}"

    def assess_data_quality(
        self,
        data: list[dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        expected_interval_minutes: int = 1,
    ) -> DataQualityMetrics:
        """
        评估数据质量，判断是否需要插值以及推荐的预测粒度。

        Args:
            data: 原始监测数据列表
            start_time: 数据期望的开始时间
            end_time: 数据期望的结束时间
            expected_interval_minutes: 期望的数据上报间隔（分钟）

        Returns:
            数据质量评估结果
        """
        if not data:
            return DataQualityMetrics(
                total_expected_points=0,
                actual_points=0,
                coverage_rate=0.0,
                missing_hours=list(range(24)),
                data_gaps=[(start_time, end_time)],
                recommended_granularity=PredictionGranularity.DAILY,
                interpolation_needed=False,
                quality_score=0.0,
            )

        # 转换为 DataFrame
        df = self._to_dataframe(data)
        if df.empty:
            return DataQualityMetrics(
                total_expected_points=0,
                actual_points=0,
                coverage_rate=0.0,
                missing_hours=list(range(24)),
                data_gaps=[(start_time, end_time)],
                recommended_granularity=PredictionGranularity.DAILY,
                interpolation_needed=False,
                quality_score=0.0,
            )

        # 计算期望数据点数
        time_span_minutes = (end_time - start_time).total_seconds() / 60
        expected_points = int(time_span_minutes / expected_interval_minutes)
        actual_points = len(df)

        # 计算覆盖率
        coverage_rate = actual_points / expected_points if expected_points > 0 else 0.0

        # 检测缺失的小时
        df_hourly = df.set_index("ts").resample("h").count()
        hours_with_data = set(df_hourly[df_hourly["value"] > 0].index.hour)
        all_hours = set(range(24))
        missing_hours = sorted(list(all_hours - hours_with_data))

        # 检测数据断档
        data_gaps = self._detect_gaps(df, max_gap_minutes=self.max_interpolation_gap)

        # 计算每小时的数据密度
        hourly_counts = df.set_index("ts").resample("h")["value"].count()
        hours_with_sufficient_data = (hourly_counts >= self.MIN_POINTS_PER_HOUR).sum()
        total_hours = len(hourly_counts)
        hourly_coverage = hours_with_sufficient_data / total_hours if total_hours > 0 else 0.0

        # 推荐预测粒度
        if hourly_coverage >= self.HOURLY_MIN_COVERAGE and coverage_rate >= 0.4:
            recommended_granularity = PredictionGranularity.HOURLY
        elif coverage_rate >= self.DAILY_MIN_COVERAGE:
            recommended_granularity = PredictionGranularity.DAILY
        else:
            recommended_granularity = PredictionGranularity.DAILY

        # 是否需要插值
        interpolation_needed = coverage_rate < 0.9 and coverage_rate >= self.DAILY_MIN_COVERAGE

        # 综合质量评分
        quality_score = self._calculate_quality_score(
            coverage_rate=coverage_rate,
            hourly_coverage=hourly_coverage,
            gap_count=len(data_gaps),
            missing_hour_count=len(missing_hours),
        )

        metrics = DataQualityMetrics(
            total_expected_points=expected_points,
            actual_points=actual_points,
            coverage_rate=coverage_rate,
            missing_hours=missing_hours,
            data_gaps=data_gaps,
            recommended_granularity=recommended_granularity,
            interpolation_needed=interpolation_needed,
            quality_score=quality_score,
        )

        logger.info(
            "Data quality assessed",
            actual_points=actual_points,
            expected_points=expected_points,
            coverage_rate=f"{coverage_rate:.2%}",
            recommended_granularity=recommended_granularity.value,
            quality_score=quality_score,
        )

        return metrics

    def interpolate(
        self,
        data: list[dict[str, Any]],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        target_interval: Optional[str] = None,
        method: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        对时序数据进行插值填充。

        Args:
            data: 原始监测数据列表
            start_time: 可选，指定插值的开始时间
            end_time: 可选，指定插值的结束时间
            target_interval: 可选，覆盖默认的目标采样间隔
            method: 可选，覆盖默认的插值方法

        Returns:
            插值后的 DataFrame，包含 ts, value 列
        """
        if not data:
            return pd.DataFrame(columns=["ts", "value"])

        df = self._to_dataframe(data)
        if df.empty:
            return pd.DataFrame(columns=["ts", "value"])

        interval = self._normalize_frequency(target_interval or self.target_interval)
        interp_method = method or self.interpolation_method

        # 设置时间索引
        df = df.set_index("ts")

        # 确定时间范围
        data_start = df.index.min()
        data_end = df.index.max()
        fill_start = start_time if start_time and start_time < data_start else data_start
        fill_end = end_time if end_time and end_time > data_end else data_end

        # 创建完整的时间索引
        full_index = pd.date_range(start=fill_start, end=fill_end, freq=interval)

        # 重新索引并填充
        df_reindexed = df.reindex(full_index)

        # 检测大的数据断档，标记为不应插值
        gap_mask = self._create_gap_mask(df_reindexed, max_gap_minutes=self.max_interpolation_gap)

        # 执行插值
        if interp_method == "spline":
            # 样条插值需要足够的数据点
            if len(df) >= 4:
                df_interpolated = df_reindexed.interpolate(method="spline", order=3)
            else:
                df_interpolated = df_reindexed.interpolate(method="linear")
        elif interp_method in ["pad", "ffill"]:
            df_interpolated = df_reindexed.ffill(limit=10)
        elif interp_method == "nearest":
            df_interpolated = df_reindexed.interpolate(method="nearest")
        else:  # linear (default)
            df_interpolated = df_reindexed.interpolate(method="linear")

        # 对于大断档区域，使用 NaN 或最近有效值
        if gap_mask is not None:
            df_interpolated.loc[gap_mask, "value"] = np.nan

        # 填充边界值（使用前向/后向填充）
        df_interpolated = df_interpolated.bfill(limit=5)
        df_interpolated = df_interpolated.ffill(limit=5)

        # 重置索引
        df_result = df_interpolated.reset_index()
        df_result.columns = ["ts", "value"]

        # 过滤掉仍然为 NaN 的值
        df_result = df_result.dropna(subset=["value"])

        logger.info(
            "Data interpolation completed",
            original_points=len(df),
            interpolated_points=len(df_result),
            interval=interval,
            method=interp_method,
        )

        return df_result

    def interpolate_hourly(
        self,
        data: list[dict[str, Any]],
        target_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        生成小时级聚合数据（带插值）。

        用于 AI 诊断报告的小时级统计数据生成。

        Args:
            data: 原始监测数据列表
            target_date: 可选，指定日期（用于确定24小时范围）

        Returns:
            小时级聚合 DataFrame，包含 hour, mean, max, min, count 列
        """
        if not data:
            return pd.DataFrame(columns=["hour", "mean", "max", "min", "count"])

        df = self._to_dataframe(data)
        if df.empty:
            return pd.DataFrame(columns=["hour", "mean", "max", "min", "count"])

        # 先进行分钟级插值
        df_interpolated = self.interpolate(data, target_interval="5min")

        if df_interpolated.empty:
            return pd.DataFrame(columns=["hour", "mean", "max", "min", "count"])

        # 按小时聚合
        df_interpolated = df_interpolated.set_index("ts")
        hourly = df_interpolated["value"].resample("h").agg(["mean", "max", "min", "count"])
        hourly = hourly.reset_index()
        hourly["hour"] = hourly["ts"].dt.strftime("%H:00")

        # 如果指定了日期，确保有完整的24小时
        if target_date:
            full_hours = pd.date_range(
                start=datetime.combine(target_date, datetime.min.time()),
                end=datetime.combine(target_date, datetime.max.time()),
                freq="h",
            )
            hourly_full = pd.DataFrame({"ts": full_hours})
            hourly_full["hour"] = hourly_full["ts"].dt.strftime("%H:00")
            hourly = hourly_full.merge(
                hourly[["hour", "mean", "max", "min", "count"]],
                on="hour",
                how="left",
            )

        # 对缺失小时进行插值（仅对均值）
        if hourly["mean"].isna().any():
            hourly["mean"] = hourly["mean"].interpolate(method="linear")
            hourly["max"] = hourly["max"].interpolate(method="linear")
            hourly["min"] = hourly["min"].interpolate(method="linear")
            hourly["count"] = hourly["count"].fillna(0).astype(int)

        result = hourly[["hour", "mean", "max", "min", "count"]].copy()
        result["mean"] = result["mean"].round(2)
        result["max"] = result["max"].round(2)
        result["min"] = result["min"].round(2)

        logger.info(
            "Hourly interpolation completed",
            original_points=len(data),
            hourly_points=len(result),
            hours_with_data=(result["count"] > 0).sum(),
        )

        return result

    def prepare_for_prediction(
        self,
        data: list[dict[str, Any]],
        granularity: PredictionGranularity = PredictionGranularity.HOURLY,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """
        为时序预测准备数据（包含插值和粒度调整）。

        Args:
            data: 原始监测数据列表
            granularity: 预测粒度

        Returns:
            (预处理后的 DataFrame, 预处理元数据)
        """
        if not data:
            return pd.DataFrame(columns=["ds", "y"]), {"error": "no_data"}

        # 根据粒度选择采样间隔
        interval_map = {
            PredictionGranularity.MINUTE_15: "15min",
            PredictionGranularity.HOURLY: "1h",
            PredictionGranularity.DAILY: "1D",
        }
        target_interval = interval_map.get(granularity, "1h")

        # 执行插值
        df_interpolated = self.interpolate(data, target_interval=target_interval)

        if df_interpolated.empty:
            return pd.DataFrame(columns=["ds", "y"]), {"error": "interpolation_failed"}

        # 转换为 Prophet 格式
        df_prophet = df_interpolated.rename(columns={"ts": "ds", "value": "y"})

        # 如果是日级粒度，需要按日聚合
        if granularity == PredictionGranularity.DAILY:
            df_prophet = df_prophet.set_index("ds")
            df_prophet = df_prophet.resample("D").mean().reset_index()

        metadata = {
            "granularity": granularity.value,
            "interval": target_interval,
            "original_points": len(data),
            "processed_points": len(df_prophet),
            "interpolation_method": self.interpolation_method,
        }

        logger.info(
            "Data prepared for prediction",
            granularity=granularity.value,
            processed_points=len(df_prophet),
        )

        return df_prophet, metadata

    def _to_dataframe(self, data: list[dict[str, Any]]) -> pd.DataFrame:
        """将数据列表转换为 DataFrame"""
        records = []
        for point in data:
            ts = point.get("ts") or point.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if ts is not None:
                # 移除时区信息
                if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
                try:
                    value = float(point["value"])
                    records.append({"ts": ts, "value": value})
                except (ValueError, TypeError):
                    continue

        if not records:
            return pd.DataFrame(columns=["ts", "value"])

        df = pd.DataFrame(records)
        df = df.sort_values("ts").reset_index(drop=True)
        return df

    def _detect_gaps(
        self,
        df: pd.DataFrame,
        max_gap_minutes: int = 120,
    ) -> list[tuple[datetime, datetime]]:
        """检测数据断档"""
        if len(df) < 2:
            return []

        gaps = []
        df_sorted = df.sort_values("ts")
        timestamps = df_sorted["ts"].values

        for i in range(len(timestamps) - 1):
            current = pd.Timestamp(timestamps[i])
            next_ts = pd.Timestamp(timestamps[i + 1])
            gap_minutes = (next_ts - current).total_seconds() / 60

            if gap_minutes > max_gap_minutes:
                gaps.append((current.to_pydatetime(), next_ts.to_pydatetime()))

        return gaps

    def _create_gap_mask(
        self,
        df: pd.DataFrame,
        max_gap_minutes: int = 120,
    ) -> Optional[pd.Series]:
        """创建大断档区域的掩码"""
        if df.empty:
            return None

        # 找到原始非空值的位置
        non_null_mask = df["value"].notna()
        non_null_indices = df.index[non_null_mask]

        if len(non_null_indices) < 2:
            return None

        gap_mask = pd.Series(False, index=df.index)
        max_gap = pd.Timedelta(minutes=max_gap_minutes)

        for i in range(len(non_null_indices) - 1):
            current_idx = non_null_indices[i]
            next_idx = non_null_indices[i + 1]
            gap = next_idx - current_idx

            if gap > max_gap:
                # 标记这个区间内的所有点
                gap_mask.loc[current_idx:next_idx] = True

        return gap_mask if gap_mask.any() else None

    def _calculate_quality_score(
        self,
        coverage_rate: float,
        hourly_coverage: float,
        gap_count: int,
        missing_hour_count: int,
    ) -> float:
        """计算综合数据质量评分 (0-100)"""
        # 权重分配
        coverage_weight = 0.4
        hourly_weight = 0.3
        gap_penalty = 0.2
        hour_penalty = 0.1

        # 覆盖率得分 (0-100)
        coverage_score = coverage_rate * 100

        # 小时覆盖得分 (0-100)
        hourly_score = hourly_coverage * 100

        # 断档惩罚 (每个断档扣5分，最多扣50分)
        gap_deduction = min(gap_count * 5, 50)

        # 缺失小时惩罚 (每小时扣2分，最多扣48分)
        hour_deduction = min(missing_hour_count * 2, 48)

        # 综合得分
        score = (
            coverage_score * coverage_weight +
            hourly_score * hourly_weight -
            gap_deduction * gap_penalty -
            hour_deduction * hour_penalty
        )

        return max(0.0, min(100.0, score))


# 便捷函数
def interpolate_monitoring_data(
    data: list[dict[str, Any]],
    target_interval: str = "5min",
    method: str = "linear",
) -> pd.DataFrame:
    """
    便捷函数：对监测数据进行插值填充。

    Args:
        data: 原始监测数据列表
        target_interval: 目标采样间隔
        method: 插值方法

    Returns:
        插值后的 DataFrame
    """
    interpolator = DataInterpolator(
        target_interval=target_interval,
        interpolation_method=method,
    )
    return interpolator.interpolate(data)


def assess_and_recommend_granularity(
    data: list[dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
) -> tuple[PredictionGranularity, DataQualityMetrics]:
    """
    便捷函数：评估数据质量并推荐预测粒度。

    Args:
        data: 原始监测数据列表
        start_time: 期望的开始时间
        end_time: 期望的结束时间

    Returns:
        (推荐粒度, 质量指标)
    """
    interpolator = DataInterpolator()
    metrics = interpolator.assess_data_quality(data, start_time, end_time)
    return metrics.recommended_granularity, metrics
