"""
Monitoring and analytics tools for LangChain
"""

from typing import Any, Dict, List, Optional, Type, Tuple
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import random
import numpy as np
from collections import defaultdict

from .base import BaseNetworkTool, CachedToolMixin


class MetricsQueryInput(BaseModel):
    """Input for metrics query"""
    metric_type: str = Field(description="Type of metric: cpu, memory, disk, network, custom")
    target: Optional[str] = Field(None, description="Target device or service")
    time_range: str = Field(default="1h", description="Time range: 1h, 6h, 24h, 7d, 30d")
    aggregation: str = Field(default="avg", description="Aggregation: avg, max, min, sum")


class MetricsQueryTool(BaseNetworkTool, CachedToolMixin):
    """Tool for querying monitoring metrics"""
    
    name: str = "metrics_query"
    description: str = "Query monitoring metrics for devices and services"
    args_schema: Type[BaseModel] = MetricsQueryInput
    
    def _execute(self, metric_type: str, target: Optional[str] = None, 
                 time_range: str = "1h", aggregation: str = "avg", timeout: int = 30) -> Dict[str, Any]:
        """Query metrics"""
        # Parse time range
        end_time = datetime.now()
        start_time = self._parse_time_range(end_time, time_range)
        
        # Check cache
        cache_key = f"{metric_type}_{target}_{time_range}_{aggregation}"
        cached = self.get_cached_result(cache_key)
        if cached:
            return cached
        
        # Query metrics (simulated)
        metrics_data = self._query_metrics(metric_type, target, start_time, end_time)
        
        # Aggregate data
        aggregated = self._aggregate_metrics(metrics_data, aggregation)
        
        # Analyze trends
        analysis = self._analyze_metrics(metrics_data)
        
        result = {
            "metric_type": metric_type,
            "target": target or "all",
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration": time_range
            },
            "aggregation": aggregation,
            "data": aggregated,
            "analysis": analysis
        }
        
        # Cache result
        self.cache_result(cache_key, result)
        
        return result
    
    def _parse_time_range(self, end_time: datetime, time_range: str) -> datetime:
        """Parse time range string to datetime"""
        units = {
            'h': 'hours',
            'd': 'days',
            'm': 'minutes'
        }
        
        # Extract number and unit
        import re
        match = re.match(r'(\d+)([hdm])', time_range)
        if match:
            value = int(match.group(1))
            unit = units.get(match.group(2), 'hours')
            delta = timedelta(**{unit: value})
            return end_time - delta
        
        # Default to 1 hour
        return end_time - timedelta(hours=1)
    
    def _query_metrics(self, metric_type: str, target: Optional[str], 
                      start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Query metrics from monitoring system"""
        # In production, this would query Prometheus/InfluxDB
        # For demo, generate sample data
        
        data_points = []
        current_time = start_time
        interval = timedelta(minutes=5)
        
        while current_time <= end_time:
            if metric_type == "cpu":
                value = 30 + random.uniform(-10, 40) + (10 if current_time.hour in [9, 10, 11, 14, 15] else 0)
            elif metric_type == "memory":
                value = 60 + random.uniform(-5, 20)
            elif metric_type == "disk":
                value = 70 + random.uniform(-2, 5)
            elif metric_type == "network":
                value = random.uniform(10, 100)
            else:
                value = random.uniform(0, 100)
            
            data_points.append({
                "timestamp": current_time.isoformat(),
                "value": round(value, 2),
                "target": target or "system"
            })
            
            current_time += interval
        
        return data_points
    
    def _aggregate_metrics(self, data: List[Dict[str, Any]], aggregation: str) -> Dict[str, Any]:
        """Aggregate metrics data"""
        if not data:
            return {"error": "No data available"}
        
        values = [d["value"] for d in data]
        
        aggregations = {
            "avg": np.mean(values),
            "max": np.max(values),
            "min": np.min(values),
            "sum": np.sum(values),
            "count": len(values),
            "std": np.std(values),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99)
        }
        
        return {
            "value": round(aggregations.get(aggregation, aggregations["avg"]), 2),
            "all_aggregations": {k: round(v, 2) for k, v in aggregations.items()},
            "data_points": len(data),
            "latest_value": data[-1]["value"] if data else None
        }
    
    def _analyze_metrics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze metrics for trends and anomalies"""
        if len(data) < 2:
            return {"trend": "insufficient_data"}
        
        values = [d["value"] for d in data]
        timestamps = [datetime.fromisoformat(d["timestamp"]) for d in data]
        
        # Calculate trend
        x = np.arange(len(values))
        coefficients = np.polyfit(x, values, 1)
        trend_slope = coefficients[0]
        
        # Determine trend direction
        if abs(trend_slope) < 0.1:
            trend = "stable"
        elif trend_slope > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        
        # Find anomalies (simple threshold-based)
        mean = np.mean(values)
        std = np.std(values)
        anomalies = []
        
        for i, value in enumerate(values):
            if abs(value - mean) > 2 * std:
                anomalies.append({
                    "timestamp": data[i]["timestamp"],
                    "value": value,
                    "deviation": round(abs(value - mean) / std, 2)
                })
        
        return {
            "trend": trend,
            "trend_slope": round(trend_slope, 3),
            "volatility": round(std / mean * 100, 2) if mean > 0 else 0,
            "anomalies_detected": len(anomalies),
            "anomalies": anomalies[:5]  # Limit to 5 most recent
        }


class AlertManagementInput(BaseModel):
    """Input for alert management"""
    action: str = Field(description="Action: list, acknowledge, resolve, create")
    alert_id: Optional[str] = Field(None, description="Alert ID for acknowledge/resolve")
    severity: Optional[str] = Field(None, description="Filter by severity: critical, warning, info")
    active_only: bool = Field(default=True, description="Show only active alerts")


class AlertManagementTool(BaseNetworkTool):
    """Tool for managing alerts"""
    
    name: str = "alert_management"
    description: str = "Manage monitoring alerts - view, acknowledge, and resolve"
    args_schema: Type[BaseModel] = AlertManagementInput
    
    # In-memory alert storage (in production, this would be a database)
    _alerts: List[Dict[str, Any]] = []
    
    def _execute(self, action: str, alert_id: Optional[str] = None, 
                 severity: Optional[str] = None, active_only: bool = True, timeout: int = 30) -> Dict[str, Any]:
        """Manage alerts"""
        if action == "list":
            return self._list_alerts(severity, active_only)
        elif action == "acknowledge":
            return self._acknowledge_alert(alert_id)
        elif action == "resolve":
            return self._resolve_alert(alert_id)
        elif action == "create":
            return {"error": "Use alert creation through monitoring rules"}
        else:
            return {"error": f"Invalid action: {action}"}
    
    def _list_alerts(self, severity: Optional[str], active_only: bool) -> Dict[str, Any]:
        """List alerts"""
        # Generate sample alerts if empty
        if not self._alerts:
            self._generate_sample_alerts()
        
        # Filter alerts
        filtered_alerts = self._alerts
        
        if severity:
            filtered_alerts = [a for a in filtered_alerts if a["severity"] == severity]
        
        if active_only:
            filtered_alerts = [a for a in filtered_alerts if a["status"] == "active"]
        
        # Group by severity
        by_severity = defaultdict(list)
        for alert in filtered_alerts:
            by_severity[alert["severity"]].append(alert)
        
        return {
            "total_alerts": len(filtered_alerts),
            "by_severity": {
                "critical": len(by_severity["critical"]),
                "warning": len(by_severity["warning"]),
                "info": len(by_severity["info"])
            },
            "alerts": sorted(filtered_alerts, key=lambda x: x["created_at"], reverse=True)[:20]
        }
    
    def _acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        """Acknowledge an alert"""
        if not alert_id:
            return {"error": "Alert ID required"}
        
        for alert in self._alerts:
            if alert["id"] == alert_id:
                alert["status"] = "acknowledged"
                alert["acknowledged_at"] = datetime.now().isoformat()
                return {
                    "success": True,
                    "alert_id": alert_id,
                    "message": "Alert acknowledged"
                }
        
        return {"error": f"Alert {alert_id} not found"}
    
    def _resolve_alert(self, alert_id: str) -> Dict[str, Any]:
        """Resolve an alert"""
        if not alert_id:
            return {"error": "Alert ID required"}
        
        for alert in self._alerts:
            if alert["id"] == alert_id:
                alert["status"] = "resolved"
                alert["resolved_at"] = datetime.now().isoformat()
                return {
                    "success": True,
                    "alert_id": alert_id,
                    "message": "Alert resolved"
                }
        
        return {"error": f"Alert {alert_id} not found"}
    
    def _generate_sample_alerts(self):
        """Generate sample alerts"""
        alert_templates = [
            {
                "name": "High CPU Usage",
                "severity": "warning",
                "description": "CPU usage above 80% on {target}",
                "metric": "cpu_usage",
                "threshold": 80
            },
            {
                "name": "Disk Space Low",
                "severity": "critical",
                "description": "Disk space below 10% on {target}",
                "metric": "disk_free",
                "threshold": 10
            },
            {
                "name": "Memory Pressure",
                "severity": "warning",
                "description": "Memory usage above 90% on {target}",
                "metric": "memory_usage",
                "threshold": 90
            },
            {
                "name": "Service Down",
                "severity": "critical",
                "description": "Service {service} is down on {target}",
                "metric": "service_status",
                "threshold": 0
            },
            {
                "name": "Network Latency",
                "severity": "info",
                "description": "Network latency above 100ms to {target}",
                "metric": "network_latency",
                "threshold": 100
            }
        ]
        
        targets = ["server-01", "server-02", "database-01", "web-01"]
        
        for i in range(10):
            template = random.choice(alert_templates)
            target = random.choice(targets)
            
            alert = {
                "id": f"alert_{i+1:04d}",
                "name": template["name"],
                "severity": template["severity"],
                "description": template["description"].format(
                    target=target,
                    service=random.choice(["nginx", "mysql", "redis"])
                ),
                "target": target,
                "metric": template["metric"],
                "threshold": template["threshold"],
                "current_value": template["threshold"] + random.uniform(-10, 20),
                "status": random.choice(["active", "active", "acknowledged", "resolved"]),
                "created_at": (datetime.now() - timedelta(minutes=random.randint(1, 1440))).isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            self._alerts.append(alert)


class PerformanceAnalysisInput(BaseModel):
    """Input for performance analysis"""
    target: str = Field(description="Target device or service to analyze")
    analysis_type: str = Field(default="comprehensive", description="Type: comprehensive, cpu, memory, disk, network")
    time_range: str = Field(default="24h", description="Time range for analysis")


class PerformanceAnalysisTool(BaseNetworkTool):
    """Tool for performance analysis"""
    
    name: str = "performance_analysis"
    description: str = "Analyze system performance and provide insights and recommendations"
    args_schema: Type[BaseModel] = PerformanceAnalysisInput
    
    def _execute(self, target: str, analysis_type: str = "comprehensive", 
                 time_range: str = "24h", timeout: int = 30) -> Dict[str, Any]:
        """Perform performance analysis"""
        # Gather metrics for analysis
        metrics = self._gather_performance_metrics(target, analysis_type, time_range)
        
        # Analyze performance
        analysis = self._analyze_performance(metrics)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(analysis)
        
        return {
            "target": target,
            "analysis_type": analysis_type,
            "time_range": time_range,
            "timestamp": datetime.now().isoformat(),
            "metrics_summary": metrics,
            "analysis": analysis,
            "recommendations": recommendations,
            "health_score": self._calculate_health_score(analysis)
        }
    
    def _gather_performance_metrics(self, target: str, analysis_type: str, time_range: str) -> Dict[str, Any]:
        """Gather performance metrics"""
        metrics = {}
        
        if analysis_type in ["comprehensive", "cpu"]:
            metrics["cpu"] = {
                "average_usage": 65.2,
                "peak_usage": 92.5,
                "idle_percentage": 34.8,
                "load_average": [2.1, 1.8, 1.5]
            }
        
        if analysis_type in ["comprehensive", "memory"]:
            metrics["memory"] = {
                "average_usage": 78.3,
                "peak_usage": 89.2,
                "swap_usage": 12.5,
                "cache_hit_rate": 94.2
            }
        
        if analysis_type in ["comprehensive", "disk"]:
            metrics["disk"] = {
                "iops_read": 245,
                "iops_write": 189,
                "throughput_mb_s": 125.4,
                "latency_ms": 2.3,
                "usage_percentage": 72.1
            }
        
        if analysis_type in ["comprehensive", "network"]:
            metrics["network"] = {
                "bandwidth_in_mbps": 85.2,
                "bandwidth_out_mbps": 62.1,
                "packet_loss": 0.02,
                "latency_ms": 1.2,
                "connections_active": 342
            }
        
        return metrics
    
    def _analyze_performance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance metrics"""
        analysis = {}
        
        # CPU Analysis
        if "cpu" in metrics:
            cpu = metrics["cpu"]
            analysis["cpu"] = {
                "status": "warning" if cpu["average_usage"] > 70 else "healthy",
                "issues": []
            }
            
            if cpu["average_usage"] > 70:
                analysis["cpu"]["issues"].append("High average CPU usage")
            if cpu["peak_usage"] > 90:
                analysis["cpu"]["issues"].append("CPU peaks above 90%")
        
        # Memory Analysis
        if "memory" in metrics:
            mem = metrics["memory"]
            analysis["memory"] = {
                "status": "critical" if mem["average_usage"] > 85 else "warning" if mem["average_usage"] > 70 else "healthy",
                "issues": []
            }
            
            if mem["average_usage"] > 85:
                analysis["memory"]["issues"].append("Critical memory usage")
            if mem["swap_usage"] > 20:
                analysis["memory"]["issues"].append("High swap usage indicating memory pressure")
        
        # Disk Analysis
        if "disk" in metrics:
            disk = metrics["disk"]
            analysis["disk"] = {
                "status": "healthy",
                "issues": []
            }
            
            if disk["latency_ms"] > 10:
                analysis["disk"]["issues"].append("High disk latency")
                analysis["disk"]["status"] = "warning"
        
        # Network Analysis
        if "network" in metrics:
            net = metrics["network"]
            analysis["network"] = {
                "status": "healthy" if net["packet_loss"] < 0.1 else "warning",
                "issues": []
            }
            
            if net["packet_loss"] > 0.1:
                analysis["network"]["issues"].append("Network packet loss detected")
        
        return analysis
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance recommendations"""
        recommendations = []
        
        # CPU recommendations
        if "cpu" in analysis and analysis["cpu"]["status"] != "healthy":
            recommendations.append({
                "category": "cpu",
                "priority": "high" if analysis["cpu"]["status"] == "critical" else "medium",
                "recommendation": "Consider scaling horizontally or optimizing CPU-intensive processes",
                "actions": [
                    "Identify top CPU consumers using process monitoring",
                    "Review application code for optimization opportunities",
                    "Consider implementing load balancing"
                ]
            })
        
        # Memory recommendations
        if "memory" in analysis and analysis["memory"]["status"] != "healthy":
            recommendations.append({
                "category": "memory",
                "priority": "high" if analysis["memory"]["status"] == "critical" else "medium",
                "recommendation": "Address memory usage to prevent performance degradation",
                "actions": [
                    "Analyze memory leaks in applications",
                    "Increase system memory if consistently high",
                    "Optimize memory-intensive operations",
                    "Review and adjust memory limits for services"
                ]
            })
        
        # General optimization
        recommendations.append({
            "category": "general",
            "priority": "low",
            "recommendation": "Regular maintenance and monitoring",
            "actions": [
                "Set up automated alerting for resource thresholds",
                "Schedule regular performance reviews",
                "Implement capacity planning procedures"
            ]
        })
        
        return recommendations
    
    def _calculate_health_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate overall health score (0-100)"""
        score = 100
        
        for component, data in analysis.items():
            if data["status"] == "critical":
                score -= 30
            elif data["status"] == "warning":
                score -= 15
            
            # Deduct for specific issues
            score -= len(data.get("issues", [])) * 5
        
        return max(0, score)


class PredictiveMaintenanceInput(BaseModel):
    """Input for predictive maintenance"""
    target: str = Field(description="Target device or system")
    prediction_window: str = Field(default="7d", description="Prediction window: 24h, 7d, 30d")


class PredictiveMaintenanceTool(BaseNetworkTool):
    """Tool for predictive maintenance analysis"""
    
    name: str = "predictive_maintenance"
    description: str = "Predict potential failures and maintenance needs using historical data and trends"
    args_schema: Type[BaseModel] = PredictiveMaintenanceInput
    
    def _execute(self, target: str, prediction_window: str = "7d", timeout: int = 30) -> Dict[str, Any]:
        """Perform predictive maintenance analysis"""
        # Analyze historical data
        historical_analysis = self._analyze_historical_data(target)
        
        # Generate predictions
        predictions = self._generate_predictions(target, prediction_window, historical_analysis)
        
        # Calculate risk scores
        risk_assessment = self._assess_risks(predictions)
        
        # Generate maintenance schedule
        maintenance_schedule = self._generate_maintenance_schedule(predictions, risk_assessment)
        
        return {
            "target": target,
            "prediction_window": prediction_window,
            "analysis_timestamp": datetime.now().isoformat(),
            "historical_analysis": historical_analysis,
            "predictions": predictions,
            "risk_assessment": risk_assessment,
            "maintenance_schedule": maintenance_schedule,
            "summary": self._generate_summary(predictions, risk_assessment)
        }
    
    def _analyze_historical_data(self, target: str) -> Dict[str, Any]:
        """Analyze historical data for patterns"""
        return {
            "failure_history": [
                {
                    "date": (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"),
                    "component": "disk",
                    "severity": "minor",
                    "downtime_hours": 0.5
                },
                {
                    "date": (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d"),
                    "component": "memory",
                    "severity": "major",
                    "downtime_hours": 2.0
                }
            ],
            "maintenance_history": [
                {
                    "date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "type": "preventive",
                    "components": ["disk", "memory"]
                }
            ],
            "performance_trends": {
                "cpu_degradation_rate": 0.02,  # 2% per month
                "disk_wear_rate": 0.05,  # 5% per month
                "memory_error_rate": 0.001  # 0.1% error rate
            }
        }
    
    def _generate_predictions(self, target: str, window: str, historical: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate failure predictions"""
        predictions = []
        
        # Disk failure prediction
        disk_prediction = {
            "component": "disk",
            "failure_probability": 0.15,  # 15% chance
            "estimated_time_to_failure": "21 days",
            "confidence": 0.82,
            "indicators": [
                "Increasing read/write errors",
                "SMART status warnings",
                "Performance degradation trend"
            ]
        }
        predictions.append(disk_prediction)
        
        # Memory prediction
        memory_prediction = {
            "component": "memory",
            "failure_probability": 0.08,  # 8% chance
            "estimated_time_to_failure": "45 days",
            "confidence": 0.75,
            "indicators": [
                "Increasing ECC error corrections",
                "Memory test failures"
            ]
        }
        predictions.append(memory_prediction)
        
        # Power supply prediction
        power_prediction = {
            "component": "power_supply",
            "failure_probability": 0.05,  # 5% chance
            "estimated_time_to_failure": "90 days",
            "confidence": 0.65,
            "indicators": [
                "Voltage fluctuations",
                "Temperature increases"
            ]
        }
        predictions.append(power_prediction)
        
        return predictions
    
    def _assess_risks(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess risks based on predictions"""
        high_risk = [p for p in predictions if p["failure_probability"] > 0.1]
        medium_risk = [p for p in predictions if 0.05 <= p["failure_probability"] <= 0.1]
        low_risk = [p for p in predictions if p["failure_probability"] < 0.05]
        
        overall_risk = "high" if high_risk else "medium" if medium_risk else "low"
        
        return {
            "overall_risk_level": overall_risk,
            "high_risk_components": len(high_risk),
            "medium_risk_components": len(medium_risk),
            "low_risk_components": len(low_risk),
            "recommended_action": "immediate" if overall_risk == "high" else "scheduled",
            "business_impact": {
                "potential_downtime_hours": sum(p["failure_probability"] * 4 for p in predictions),
                "revenue_impact_estimate": "$" + str(int(sum(p["failure_probability"] * 10000 for p in predictions)))
            }
        }
    
    def _generate_maintenance_schedule(self, predictions: List[Dict[str, Any]], risks: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate maintenance schedule based on predictions"""
        schedule = []
        
        for pred in sorted(predictions, key=lambda x: x["failure_probability"], reverse=True):
            if pred["failure_probability"] > 0.1:
                # High risk - schedule soon
                schedule_date = datetime.now() + timedelta(days=7)
            elif pred["failure_probability"] > 0.05:
                # Medium risk - schedule within month
                schedule_date = datetime.now() + timedelta(days=30)
            else:
                # Low risk - regular maintenance
                schedule_date = datetime.now() + timedelta(days=90)
            
            schedule.append({
                "component": pred["component"],
                "recommended_date": schedule_date.strftime("%Y-%m-%d"),
                "maintenance_type": "preventive" if pred["failure_probability"] < 0.1 else "corrective",
                "estimated_duration_hours": 2 if pred["component"] == "disk" else 1,
                "priority": "high" if pred["failure_probability"] > 0.1 else "medium"
            })
        
        return schedule
    
    def _generate_summary(self, predictions: List[Dict[str, Any]], risks: Dict[str, Any]) -> str:
        """Generate summary of predictive maintenance analysis"""
        high_risk_components = [p["component"] for p in predictions if p["failure_probability"] > 0.1]
        
        if risks["overall_risk_level"] == "high":
            summary = f"HIGH RISK: Immediate maintenance recommended for {', '.join(high_risk_components)}. "
            summary += f"Potential downtime of {risks['business_impact']['potential_downtime_hours']:.1f} hours if not addressed."
        elif risks["overall_risk_level"] == "medium":
            summary = "MEDIUM RISK: Schedule maintenance within 30 days to prevent potential failures."
        else:
            summary = "LOW RISK: System is healthy. Continue regular maintenance schedule."
        
        return summary