# -*- coding: utf-8 -*-
"""可视化数据生成器 (VisualizationGenerator) 的主实现文件。

包含 VisualizationGenerator 类，该类封装了从 MemoryBankManager
获取学习数据，并将其转换为特定前端可视化库（如 ECharts, D3.js）
所需数据结构（如图谱的节点和边、仪表盘数据）的逻辑。
"""
from datetime import datetime  # For progress dashboard update_time
from typing import Any, Dict, Optional

from src.config_manager.config_manager import ConfigManager

# Import real dependencies
from src.memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.monitoring_manager.monitoring_manager import MonitoringManager


class VisualizationGenerator:
    """
    可视化数据生成器模块。
    根据 MemoryBankManager 提供的数据，生成前端可视化所需的数据结构。
    """

    def __init__(
        self,
        memory_bank_manager: MemoryBankManager,
        monitoring_manager: MonitoringManager,
        config_manager: ConfigManager,
    ):
        self.memory_bank_manager = memory_bank_manager
        self.monitoring_manager = monitoring_manager
        self.config_manager = config_manager
        self.monitoring_manager.log_info("VisualizationGenerator initialized") # Changed to log_info

    def get_knowledge_graph_data(self, user_id: str, depth: int = 3, root_node_id: Optional[str] = None) -> Dict[str, Any]: # Added root_node_id
        """
        生成知识图谱数据。

        Args:
            user_id: 用户ID。
            depth: 知识图谱展开深度。

        Returns:
            包含知识图谱节点和边的 JSON 数据结构。
        """
        # Updated log message to include root_node_id if present
        log_message = f"Generating knowledge graph data for user {user_id} with depth {depth}"
        if root_node_id:
            log_message += f", root {root_node_id}"
        self.monitoring_manager.log_info(log_message)
        self.monitoring_manager.record_metric(
            "visualization.graph_requests", 1, {"user_id": user_id}
        )

        # 1. 调用 MemoryBankManager 获取所有知识点及其依赖关系
        # 根据 developer_handbook/01_MemoryBankManager.md, operation "get_all_syllabus_topics"
        # 假设 user_id 不是 get_all_syllabus_topics 的直接参数，而是通过某种方式在 MBM 内部处理或不需要
        # 如果需要 user_id, payload 应为 {"user_id": user_id}
        mbm_request = {
            "operation": "get_all_kps", # Changed from get_all_syllabus_topics
            "payload": {},  # Assuming it gets all topics, user-specific filtering might happen elsewhere or not be needed for a global graph
        }
        mbm_response = self.memory_bank_manager.process_request(mbm_request)

        if mbm_response.get("status") != "success":
            self.monitoring_manager.log_error( # Changed to log_error
                "Failed to get knowledge points from MemoryBankManager for graph",
                context={"user_id": user_id, "response": mbm_response.get("message", "No message")}
            )
            return {
                "status": "error",
                "message": "Failed to retrieve knowledge data for graph.",
            }

        all_knowledge_points = mbm_response.get("data", [])
        if not isinstance(all_knowledge_points, list):  # Ensure data is a list
            self.monitoring_manager.log_error( # Changed to log_error
                "Knowledge data from MBM is not a list",
                context={"user_id": user_id, "response_data_type": str(type(all_knowledge_points))}
            )
            all_knowledge_points = []

        # 2. 处理数据，转换成图谱库所需的节点和边格式
        nodes = []
        links = []
        node_ids = set()

        # TODO: Implement depth and root_node_id filtering if required by spec
        # For now, process all points as per current mock logic

        for kp in all_knowledge_points:
            if not isinstance(kp, dict) or "id" not in kp or "title" not in kp:
                self.monitoring_manager.log_warning( # Changed to log_warning
                    f"Skipping invalid knowledge point data: {str(kp)[:100]}", # Truncate kp string
                    context={"user_id": user_id}
                )
                continue

            nodes.append(
                {
                    "id": kp["id"],
                    "name": kp.get("title", "N/A"),  # Use title for name
                    "status": kp.get("status", "unknown"),  # Get status if available
                    "metrics": {
                        "visit_count": kp.get("visit_count", 0)
                    },  # Example, if MBM provides it
                }
            )
            node_ids.add(kp["id"])

            # Dependencies are expected to be a list of strings (dependent kp_ids)
            dependencies = kp.get("dependencies", [])
            if isinstance(dependencies, list):
                for dep_id in dependencies:
                    if (
                        dep_id in node_ids
                    ):  # Ensure dependency exists among processed nodes
                        links.append(
                            {
                                "source": dep_id,
                                "target": kp["id"],
                                "relation": "dependency",  # As per spec
                                "strength": self.config_manager.get_config(
                                    "visualization.graph.default_link_strength", 0.8
                                ),
                            }
                        )
                    # else:
                    # self.monitoring_manager.record_log("warn", f"Dependency {dep_id} for {kp['id']} not found in current node set.", {"user_id": user_id})

        # 3. 调用 MonitoringManager 记录指标
        self.monitoring_manager.record_metric(
            "visualization.graph_success", 1, {"user_id": user_id}
        )
        self.monitoring_manager.record_metric(
            "visualization.graph_nodes_count", len(nodes), {"user_id": user_id}
        )
        self.monitoring_manager.record_metric(
            "visualization.graph_links_count", len(links), {"user_id": user_id}
        )

        # 4. 返回格式化后的 JSON 数据结构
        return {
            "status": "success",
            "data": {
                "nodes": nodes,
                "links": links,
                "analytics": {
                    "graph_complexity": len(links) / max(1, len(nodes)),
                    "update_time": datetime.utcnow().isoformat() + "Z",
                },
            },
            "message": "Knowledge graph data generated successfully.",
        }

    def get_progress_dashboard_data(self, user_id: str, time_period: Optional[str] = None) -> Dict[str, Any]: # Added time_period
        """
        生成进度仪表盘数据。

        Args:
            user_id: 用户ID。

        Returns:
            包含用户学习进度统计的 JSON 数据结构。
        """
        log_message = f"Generating progress dashboard data for user {user_id}"
        if time_period:
            log_message += f", period {time_period}"
        self.monitoring_manager.log_info(log_message) # Changed to log_info
        self.monitoring_manager.record_metric(
            "visualization.dashboard_requests", 1, {"user_id": user_id}
        )

        # 1. 调用 MemoryBankManager 获取所有知识点 (or user-specific if MBM supports it)
        # We'll use "get_all_syllabus_topics" and then filter/process for the user if needed,
        # or assume it returns data relevant to the user context if MBM handles user scope.
        # For simplicity, let's assume "get_all_kps" gives all KPs.
        mbm_request = {
            "operation": "get_all_kps",  # Changed from get_all_syllabus_topics. Or a more specific operation if available
            "payload": {},  # Potentially {"user_id": user_id} if MBM filters
        }
        mbm_response = self.memory_bank_manager.process_request(mbm_request)

        if mbm_response.get("status") != "success":
            self.monitoring_manager.log_error( # Changed to log_error
                "Failed to get knowledge points from MemoryBankManager for dashboard",
                context={"user_id": user_id, "response": mbm_response.get("message", "No message")}
            )
            return {
                "status": "error",
                "message": "Failed to retrieve knowledge data for dashboard.",
            }

        all_knowledge_points = mbm_response.get("data", [])
        if not isinstance(all_knowledge_points, list):
            self.monitoring_manager.log_error( # Changed to log_error
                "Knowledge data from MBM for dashboard is not a list",
                context={"user_id": user_id, "response_data_type": str(type(all_knowledge_points))}
            )
            all_knowledge_points = []

        # 2. 处理数据，进行统计汇总
        status_distribution = {
            "mastered": 0,
            "learning": 0,
            "not_started": 0,
            "review": 0,  # Assuming 'review' is a valid status
            "unknown": 0,
        }
        total_points = len(all_knowledge_points)
        # Filter for user-specific KPs if MBM doesn't do it.
        # For now, assume all_knowledge_points are relevant or global.
        # If user_id is a field in KP, filter here:
        # user_kps = [kp for kp in all_knowledge_points if kp.get("user_id") == user_id]
        # total_points = len(user_kps)
        # For now, using all_knowledge_points directly for global stats.

        for kp in all_knowledge_points:
            if not isinstance(kp, dict):
                status_distribution["unknown"] += 1
                continue
            status = kp.get("status", "unknown").lower()
            if status == "mastered":
                status_distribution["mastered"] += 1
            elif status == "learning":
                status_distribution["learning"] += 1
            elif status == "not_started":  # or "new"
                status_distribution["not_started"] += 1
            elif status == "review":  # from mock data
                status_distribution["review"] += 1
            else:
                status_distribution["unknown"] += 1

        # Calculate overall progress (e.g., mastered / total relevant points)
        # This definition of progress might need refinement based on product requirements
        # For example, 'learning' might also count towards progress.
        # Using 'mastered' / total for now.
        overall_progress = (
            (status_distribution["mastered"] / total_points * 100)
            if total_points > 0
            else 0.0
        )

        # Placeholder for recent achievements
        recent_achievements = (
            []
        )  # This would require querying MBM for recent 'mastered' KPs

        progress_data = {
            "overall_progress": round(overall_progress, 2),
            "status_distribution": status_distribution,
            "recent_achievements": recent_achievements,
            "update_time": datetime.utcnow().isoformat() + "Z",
        }

        # 3. 调用 MonitoringManager 记录指标
        self.monitoring_manager.record_metric(
            "visualization.dashboard_success", 1, {"user_id": user_id}
        )
        self.monitoring_manager.record_metric(
            "visualization.dashboard_completion_rate",
            overall_progress,
            {"user_id": user_id},
        )

        # 4. 返回格式化后的 JSON 数据结构
        return {
            "status": "success",
            "data": progress_data,
            "message": "Progress dashboard data generated successfully.",
        }


# Example usage (commented out as it relies on a running app context)
# if __name__ == "__main__":
#     # This part would require setting up mock or real MBM, Monitor, Config instances
#     # which is beyond a simple script run without the full app context.
#     pass
