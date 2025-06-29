"""
Predictive Maintenance Agent for Network Management System
Uses ML algorithms to predict failures and suggest maintenance actions
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA
import warnings
warnings.filterwarnings('ignore')

from .base import BaseNetworkAgent
# from ..tools.monitoring_tools import SystemMetricsCollector  # Not implemented yet
# from ...models.device import Device  # Not implemented yet  
# from ...services.system_metrics import get_system_metrics  # Not implemented yet


class PredictiveMaintenanceAgent(BaseNetworkAgent):
    """Agent for predictive maintenance and failure prediction"""
    
    def __init__(self):
        super().__init__(
            name="PredictiveMaintenanceAgent",
            description="Analyzes system metrics to predict failures and suggest maintenance",
            tools=[SystemMetricsCollector()]
        )
        
        # ML models
        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42
        )
        self.failure_predictor = RandomForestClassifier(
            n_estimators=100,
            random_state=42
        )
        self.scaler = StandardScaler()
        
        # Thresholds and configurations
        self.thresholds = {
            'cpu_critical': 90,
            'memory_critical': 85,
            'disk_critical': 90,
            'temperature_critical': 80,
            'network_error_rate': 0.05,
            'response_time_critical': 1000  # ms
        }
        
        # Historical data storage
        self.metrics_history = {}
        self.maintenance_history = []
        
    async def analyze_system_health(self, device_id: str) -> Dict[str, Any]:
        """Analyze overall system health and predict issues"""
        try:
            # Collect current metrics
            current_metrics = await self._collect_device_metrics(device_id)
            
            # Update history
            self._update_metrics_history(device_id, current_metrics)
            
            # Perform analyses
            health_score = self._calculate_health_score(current_metrics)
            anomalies = self._detect_anomalies(device_id)
            predictions = await self._predict_failures(device_id)
            recommendations = self._generate_recommendations(
                current_metrics, anomalies, predictions
            )
            
            return {
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "health_score": health_score,
                "status": self._get_health_status(health_score),
                "current_metrics": current_metrics,
                "anomalies": anomalies,
                "predictions": predictions,
                "recommendations": recommendations,
                "maintenance_required": len(recommendations) > 0
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing system health: {e}")
            return {
                "error": str(e),
                "device_id": device_id,
                "status": "error"
            }
    
    async def predict_mtbf(self, device_id: str) -> Dict[str, Any]:
        """Predict Mean Time Between Failures"""
        try:
            history = self.metrics_history.get(device_id, [])
            if len(history) < 30:  # Need sufficient history
                return {
                    "error": "Insufficient data for MTBF prediction",
                    "required_days": 30,
                    "current_days": len(history)
                }
            
            # Extract failure events from history
            failures = self._extract_failure_events(history)
            
            if len(failures) < 2:
                # Use statistical model for prediction
                mtbf_days = self._estimate_mtbf_statistical(history)
            else:
                # Calculate actual MTBF
                mtbf_days = self._calculate_actual_mtbf(failures)
            
            # Predict next failure
            next_failure = self._predict_next_failure(history, mtbf_days)
            
            return {
                "device_id": device_id,
                "mtbf_days": mtbf_days,
                "mtbf_hours": mtbf_days * 24,
                "confidence": self._calculate_confidence(history),
                "next_failure_prediction": next_failure,
                "historical_failures": len(failures),
                "analysis_period_days": len(history)
            }
            
        except Exception as e:
            self.logger.error(f"Error predicting MTBF: {e}")
            return {"error": str(e)}
    
    async def generate_maintenance_schedule(
        self, 
        device_ids: List[str]
    ) -> Dict[str, Any]:
        """Generate optimized maintenance schedule for multiple devices"""
        try:
            schedules = []
            
            for device_id in device_ids:
                # Analyze each device
                health = await self.analyze_system_health(device_id)
                mtbf = await self.predict_mtbf(device_id)
                
                # Determine maintenance priority
                priority = self._calculate_maintenance_priority(health, mtbf)
                
                # Schedule maintenance
                schedule = {
                    "device_id": device_id,
                    "priority": priority,
                    "health_score": health.get("health_score", 0),
                    "recommended_date": self._calculate_maintenance_date(
                        priority, mtbf
                    ),
                    "estimated_duration": self._estimate_maintenance_duration(
                        health.get("recommendations", [])
                    ),
                    "actions": health.get("recommendations", [])
                }
                
                schedules.append(schedule)
            
            # Optimize schedule to minimize downtime
            optimized = self._optimize_maintenance_schedule(schedules)
            
            return {
                "total_devices": len(device_ids),
                "maintenance_required": len([s for s in schedules if s["priority"] > 0]),
                "schedule": optimized,
                "estimated_total_downtime": sum(s["estimated_duration"] for s in optimized),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating maintenance schedule: {e}")
            return {"error": str(e)}
    
    def _calculate_health_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall health score (0-100)"""
        scores = []
        
        # CPU score
        cpu_usage = metrics.get("cpu_percent", 0)
        cpu_score = max(0, 100 - cpu_usage)
        scores.append(cpu_score * 0.25)
        
        # Memory score
        memory_usage = metrics.get("memory_percent", 0)
        memory_score = max(0, 100 - memory_usage)
        scores.append(memory_score * 0.25)
        
        # Disk score
        disk_usage = metrics.get("disk_percent", 0)
        disk_score = max(0, 100 - disk_usage)
        scores.append(disk_score * 0.20)
        
        # Temperature score (if available)
        temp = metrics.get("temperature", 50)
        temp_score = max(0, 100 - (temp / self.thresholds['temperature_critical'] * 100))
        scores.append(temp_score * 0.15)
        
        # Network health score
        error_rate = metrics.get("network_error_rate", 0)
        network_score = max(0, 100 - (error_rate * 1000))
        scores.append(network_score * 0.15)
        
        return round(sum(scores), 2)
    
    def _detect_anomalies(self, device_id: str) -> List[Dict[str, Any]]:
        """Detect anomalies using Isolation Forest"""
        history = self.metrics_history.get(device_id, [])
        if len(history) < 10:
            return []
        
        # Prepare data for anomaly detection
        df = pd.DataFrame(history)
        features = ['cpu_percent', 'memory_percent', 'disk_percent']
        
        if all(f in df.columns for f in features):
            X = df[features].values
            
            # Fit and predict
            if len(X) > 20:
                X_scaled = self.scaler.fit_transform(X)
                predictions = self.anomaly_detector.fit_predict(X_scaled)
                
                # Extract anomalies
                anomalies = []
                for i, pred in enumerate(predictions):
                    if pred == -1:  # Anomaly
                        anomalies.append({
                            "timestamp": df.iloc[i]['timestamp'],
                            "type": "multi-metric anomaly",
                            "metrics": {
                                "cpu": df.iloc[i]['cpu_percent'],
                                "memory": df.iloc[i]['memory_percent'],
                                "disk": df.iloc[i]['disk_percent']
                            },
                            "severity": "medium"
                        })
                
                return anomalies[-5:]  # Return last 5 anomalies
        
        return []
    
    async def _predict_failures(self, device_id: str) -> List[Dict[str, Any]]:
        """Predict potential failures using time series analysis"""
        predictions = []
        
        history = self.metrics_history.get(device_id, [])
        if len(history) < 20:
            return predictions
        
        # Analyze each metric trend
        df = pd.DataFrame(history)
        
        for metric in ['cpu_percent', 'memory_percent', 'disk_percent']:
            if metric in df.columns:
                # Simple trend analysis
                values = df[metric].values
                trend = self._analyze_trend(values)
                
                if trend['increasing'] and trend['slope'] > 0.5:
                    # Predict when threshold will be exceeded
                    days_to_threshold = self._predict_threshold_breach(
                        values, 
                        self.thresholds.get(f"{metric.split('_')[0]}_critical", 90)
                    )
                    
                    if days_to_threshold < 30:
                        predictions.append({
                            "metric": metric,
                            "prediction": "threshold_breach",
                            "days_until_issue": days_to_threshold,
                            "confidence": trend['confidence'],
                            "current_value": values[-1],
                            "predicted_value": self.thresholds.get(
                                f"{metric.split('_')[0]}_critical", 90
                            ),
                            "severity": self._get_severity(days_to_threshold)
                        })
        
        return predictions
    
    def _generate_recommendations(
        self,
        metrics: Dict[str, Any],
        anomalies: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate maintenance recommendations"""
        recommendations = []
        
        # Check current critical conditions
        if metrics.get("cpu_percent", 0) > self.thresholds['cpu_critical']:
            recommendations.append({
                "type": "immediate",
                "action": "CPU optimization required",
                "description": "CPU usage is critical. Consider process optimization or hardware upgrade.",
                "priority": "high"
            })
        
        if metrics.get("memory_percent", 0) > self.thresholds['memory_critical']:
            recommendations.append({
                "type": "immediate",
                "action": "Memory management needed",
                "description": "Memory usage is critical. Review memory leaks and consider upgrade.",
                "priority": "high"
            })
        
        if metrics.get("disk_percent", 0) > self.thresholds['disk_critical']:
            recommendations.append({
                "type": "immediate",
                "action": "Disk cleanup required",
                "description": "Disk space is critical. Clean up logs and temporary files.",
                "priority": "high"
            })
        
        # Add predictive recommendations
        for prediction in predictions:
            if prediction['days_until_issue'] < 7:
                recommendations.append({
                    "type": "preventive",
                    "action": f"Address {prediction['metric']} trend",
                    "description": f"{prediction['metric']} will reach critical levels in {prediction['days_until_issue']} days",
                    "priority": "medium" if prediction['days_until_issue'] > 3 else "high"
                })
        
        # Add anomaly-based recommendations
        if len(anomalies) > 3:
            recommendations.append({
                "type": "investigative",
                "action": "Investigate system instability",
                "description": f"Multiple anomalies detected ({len(anomalies)} in recent history)",
                "priority": "medium"
            })
        
        return recommendations
    
    def _analyze_trend(self, values: np.ndarray) -> Dict[str, Any]:
        """Analyze trend in time series data"""
        if len(values) < 5:
            return {"increasing": False, "slope": 0, "confidence": 0}
        
        # Simple linear regression
        x = np.arange(len(values))
        coeffs = np.polyfit(x, values, 1)
        slope = coeffs[0]
        
        # Calculate R-squared for confidence
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((values - y_pred) ** 2)
        ss_tot = np.sum((values - np.mean(values)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            "increasing": slope > 0,
            "slope": slope,
            "confidence": max(0, min(1, r_squared))
        }
    
    def _predict_threshold_breach(
        self, 
        values: np.ndarray, 
        threshold: float
    ) -> int:
        """Predict days until threshold breach"""
        if len(values) < 5:
            return 999
        
        # Fit trend
        x = np.arange(len(values))
        coeffs = np.polyfit(x, values, 1)
        
        # Extrapolate to find threshold breach
        if coeffs[0] > 0:  # Increasing trend
            days_to_threshold = (threshold - coeffs[1]) / coeffs[0] - len(values)
            return max(0, int(days_to_threshold))
        
        return 999  # No breach predicted
    
    def _get_severity(self, days: int) -> str:
        """Determine severity based on time to issue"""
        if days < 1:
            return "critical"
        elif days < 7:
            return "high"
        elif days < 30:
            return "medium"
        else:
            return "low"
    
    def _get_health_status(self, score: float) -> str:
        """Get health status from score"""
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 60:
            return "fair"
        elif score >= 40:
            return "poor"
        else:
            return "critical"
    
    async def _collect_device_metrics(self, device_id: str) -> Dict[str, Any]:
        """Collect current metrics for a device"""
        # This would integrate with your actual metrics collection
        # For now, using the system metrics as example
        metrics = await get_system_metrics()
        
        # Add device-specific context
        metrics['device_id'] = device_id
        metrics['timestamp'] = datetime.now().isoformat()
        
        return metrics
    
    def _update_metrics_history(self, device_id: str, metrics: Dict[str, Any]):
        """Update metrics history for a device"""
        if device_id not in self.metrics_history:
            self.metrics_history[device_id] = []
        
        self.metrics_history[device_id].append(metrics)
        
        # Keep only last 90 days of data
        max_entries = 90 * 24  # Hourly data for 90 days
        if len(self.metrics_history[device_id]) > max_entries:
            self.metrics_history[device_id] = self.metrics_history[device_id][-max_entries:]
    
    def _extract_failure_events(self, history: List[Dict]) -> List[datetime]:
        """Extract failure events from history"""
        failures = []
        
        for i, metrics in enumerate(history):
            # Define failure conditions
            if (metrics.get('cpu_percent', 0) > 95 or
                metrics.get('memory_percent', 0) > 95 or
                metrics.get('disk_percent', 0) > 95):
                
                # Check if it's a new failure (not continuation)
                if i == 0 or not self._is_failure(history[i-1]):
                    failures.append(datetime.fromisoformat(metrics['timestamp']))
        
        return failures
    
    def _is_failure(self, metrics: Dict) -> bool:
        """Check if metrics indicate failure state"""
        return (metrics.get('cpu_percent', 0) > 95 or
                metrics.get('memory_percent', 0) > 95 or
                metrics.get('disk_percent', 0) > 95)
    
    def _calculate_actual_mtbf(self, failures: List[datetime]) -> float:
        """Calculate actual MTBF from failure history"""
        if len(failures) < 2:
            return 0
        
        # Calculate time between failures
        deltas = []
        for i in range(1, len(failures)):
            delta = (failures[i] - failures[i-1]).total_seconds() / 86400  # Days
            deltas.append(delta)
        
        return np.mean(deltas)
    
    def _estimate_mtbf_statistical(self, history: List[Dict]) -> float:
        """Estimate MTBF using statistical methods"""
        # Calculate system stability score over time
        health_scores = []
        for metrics in history:
            score = self._calculate_health_score(metrics)
            health_scores.append(score)
        
        # Estimate based on health degradation rate
        avg_health = np.mean(health_scores)
        health_std = np.std(health_scores)
        
        # Rough estimation: higher stability = longer MTBF
        if health_std < 5:  # Very stable
            base_mtbf = 180
        elif health_std < 10:  # Stable
            base_mtbf = 90
        elif health_std < 20:  # Somewhat stable
            base_mtbf = 45
        else:  # Unstable
            base_mtbf = 30
        
        # Adjust based on average health
        adjustment = avg_health / 100
        return base_mtbf * adjustment
    
    def _predict_next_failure(
        self, 
        history: List[Dict], 
        mtbf_days: float
    ) -> Dict[str, Any]:
        """Predict next failure based on MTBF and current trends"""
        failures = self._extract_failure_events(history)
        
        if failures:
            last_failure = failures[-1]
            next_failure = last_failure + timedelta(days=mtbf_days)
        else:
            # No failures yet, estimate based on current health trend
            current_health = self._calculate_health_score(history[-1])
            days_to_failure = mtbf_days * (current_health / 100)
            next_failure = datetime.now() + timedelta(days=days_to_failure)
        
        confidence = self._calculate_confidence(history)
        
        return {
            "estimated_date": next_failure.isoformat(),
            "days_from_now": (next_failure - datetime.now()).days,
            "confidence": confidence,
            "based_on": "historical_failures" if failures else "health_trends"
        }
    
    def _calculate_confidence(self, history: List[Dict]) -> float:
        """Calculate confidence level based on data quality"""
        if len(history) < 30:
            return 0.3
        elif len(history) < 90:
            return 0.6
        elif len(history) < 180:
            return 0.8
        else:
            return 0.9
    
    def _calculate_maintenance_priority(
        self,
        health: Dict[str, Any],
        mtbf: Dict[str, Any]
    ) -> int:
        """Calculate maintenance priority (0-10)"""
        priority = 0
        
        # Health score impact
        health_score = health.get('health_score', 100)
        if health_score < 40:
            priority += 5
        elif health_score < 60:
            priority += 3
        elif health_score < 80:
            priority += 1
        
        # MTBF impact
        days_to_failure = mtbf.get('next_failure_prediction', {}).get('days_from_now', 999)
        if days_to_failure < 7:
            priority += 5
        elif days_to_failure < 30:
            priority += 3
        elif days_to_failure < 90:
            priority += 1
        
        return min(10, priority)
    
    def _calculate_maintenance_date(
        self,
        priority: int,
        mtbf: Dict[str, Any]
    ) -> str:
        """Calculate recommended maintenance date"""
        days_to_failure = mtbf.get('next_failure_prediction', {}).get('days_from_now', 999)
        
        # Schedule maintenance before predicted failure
        if priority >= 8:
            maintenance_days = min(3, days_to_failure * 0.3)
        elif priority >= 5:
            maintenance_days = min(7, days_to_failure * 0.5)
        else:
            maintenance_days = min(30, days_to_failure * 0.7)
        
        maintenance_date = datetime.now() + timedelta(days=maintenance_days)
        return maintenance_date.isoformat()
    
    def _estimate_maintenance_duration(self, recommendations: List[Dict]) -> int:
        """Estimate maintenance duration in minutes"""
        duration = 0
        
        for rec in recommendations:
            if rec['type'] == 'immediate':
                duration += 60  # 1 hour for immediate issues
            elif rec['type'] == 'preventive':
                duration += 30  # 30 min for preventive
            else:
                duration += 15  # 15 min for investigative
        
        return max(30, duration)  # Minimum 30 minutes
    
    def _optimize_maintenance_schedule(
        self,
        schedules: List[Dict]
    ) -> List[Dict]:
        """Optimize maintenance schedule to minimize total downtime"""
        # Sort by priority (highest first)
        sorted_schedules = sorted(schedules, key=lambda x: x['priority'], reverse=True)
        
        # Group maintenance windows when possible
        optimized = []
        current_window = None
        
        for schedule in sorted_schedules:
            if schedule['priority'] == 0:
                continue
                
            if current_window is None:
                current_window = schedule.copy()
                optimized.append(current_window)
            else:
                # Check if can be grouped (within 7 days)
                current_date = datetime.fromisoformat(current_window['recommended_date'])
                schedule_date = datetime.fromisoformat(schedule['recommended_date'])
                
                if abs((current_date - schedule_date).days) <= 7:
                    # Group together
                    current_window['device_ids'] = current_window.get('device_ids', [current_window['device_id']])
                    current_window['device_ids'].append(schedule['device_id'])
                    current_window['estimated_duration'] += schedule['estimated_duration']
                    current_window['actions'].extend(schedule['actions'])
                else:
                    # Start new window
                    current_window = schedule.copy()
                    optimized.append(current_window)
        
        return optimized