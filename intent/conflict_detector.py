"""
Conflict Detector for IntentSpec (SPEC-02).

Detects 8 known DevOps conflict patterns before they corrupt the spec.
"""

from enum import Enum

from intent.schema import Conflict, ConfidenceBand, IntentSpec, SpecItem


class ConflictType(str, Enum):
    """Known DevOps conflict patterns."""

    PLATFORM_CONFLICT = "platform_conflict"
    REGION_CONFLICT = "region_conflict"
    COST_VS_PERFORMANCE_CONFLICT = "cost_vs_performance_conflict"
    IAC_TOOL_CONFLICT = "iac_tool_conflict"
    CLOUD_PROVIDER_CONFLICT = "cloud_provider_conflict"
    DATABASE_CONFLICT = "database_conflict"
    ENVIRONMENT_CONFLICT = "environment_conflict"
    SECURITY_VS_CONVENIENCE_CONFLICT = "security_vs_convenience_conflict"


class ConflictDetector:
    """
    Detects semantic conflicts in IntentSpec.

    Runs after every ExtractionResult is merged into IntentSpec.
    Catches conflicts before they corrupt the canonical spec.
    """

    # Mutually exclusive compute platforms
    PLATFORM_GROUPS = {
        "container_orchestration": {"EKS", "ECS", "GKE", "AKS"},
        "serverless": {"Lambda", "Cloud Functions", "Azure Functions"},
        "vm_based": {"EC2", "Compute Engine", "Azure VMs"},
    }

    # Database paradigms
    DATABASE_TYPES = {
        "relational": {"PostgreSQL", "MySQL", "Aurora", "Cloud SQL"},
        "nosql_document": {"DynamoDB", "MongoDB", "Firestore"},
        "nosql_keyvalue": {"Redis", "Memcached", "ElastiCache"},
    }

    def detect(
        self,
        spec: IntentSpec,
        new_items: list[SpecItem],
    ) -> list[Conflict]:
        """
        Detect conflicts between existing spec and new items.

        Known conflict patterns:
        1. Platform conflict: Multiple compute platforms
        2. Region conflict: Multiple different regions
        3. Cost vs performance: Conflicting optimization goals
        4. IaC conflict: Multiple IaC tools
        5. Cloud provider conflict: Multiple cloud providers
        6. Database conflict: Incompatible database types
        7. Environment conflict: Multiple environments
        8. Security vs convenience: Conflicting security requirements

        Args:
            spec: Existing IntentSpec
            new_items: New items being added

        Returns:
            List of detected Conflict objects
        """
        conflicts = []

        for new_item in new_items:
            # Check each conflict pattern
            conflicts.extend(self._check_platform_conflict(spec, new_item))
            conflicts.extend(self._check_region_conflict(spec, new_item))
            conflicts.extend(self._check_cost_performance_conflict(spec, new_item))
            conflicts.extend(self._check_iac_tool_conflict(spec, new_item))
            conflicts.extend(self._check_cloud_provider_conflict(spec, new_item))
            conflicts.extend(self._check_database_conflict(spec, new_item))
            conflicts.extend(self._check_environment_conflict(spec, new_item))
            conflicts.extend(self._check_security_convenience_conflict(spec, new_item))

        return conflicts

    def _check_platform_conflict(
        self, spec: IntentSpec, new_item: SpecItem
    ) -> list[Conflict]:
        """Detect mutually exclusive compute platforms."""
        if new_item.key != "compute_platform":
            return []

        conflicts = []
        for existing_item in spec.items.values():
            if existing_item.key == "compute_platform" and existing_item.value != new_item.value:
                # Check if they're in different platform groups
                new_group = self._get_platform_group(new_item.value)
                existing_group = self._get_platform_group(existing_item.value)

                if new_group != existing_group or new_group is None:
                    conflict = Conflict(
                        item_a=existing_item.id,
                        item_b=new_item.id,
                        conflict_type=ConflictType.PLATFORM_CONFLICT,
                        description=(
                            f"Multiple compute platforms specified: {existing_item.value} "
                            f"and {new_item.value} are mutually exclusive."
                        ),
                        resolution_options=[
                            f"Use {existing_item.value} only",
                            f"Use {new_item.value} only",
                            "Use both in separate environments",
                        ],
                        auto_resolvable=self._can_auto_resolve(existing_item, new_item),
                        auto_resolution=self._auto_resolution_message(existing_item, new_item),
                    )
                    conflicts.append(conflict)

        return conflicts

    def _check_region_conflict(
        self, spec: IntentSpec, new_item: SpecItem
    ) -> list[Conflict]:
        """Detect multiple different regions."""
        if new_item.key != "region":
            return []

        conflicts = []
        for existing_item in spec.items.values():
            if existing_item.key == "region" and existing_item.value != new_item.value:
                conflict = Conflict(
                    item_a=existing_item.id,
                    item_b=new_item.id,
                    conflict_type=ConflictType.REGION_CONFLICT,
                    description=(
                        f"Multiple regions specified: {existing_item.value} and "
                        f"{new_item.value}. Single-region or multi-region deployment?"
                    ),
                    resolution_options=[
                        f"Deploy to {existing_item.value} only",
                        f"Deploy to {new_item.value} only",
                        "Deploy to both regions (multi-region)",
                    ],
                    auto_resolvable=self._can_auto_resolve(existing_item, new_item),
                    auto_resolution=self._auto_resolution_message(existing_item, new_item),
                )
                conflicts.append(conflict)

        return conflicts

    def _check_cost_performance_conflict(
        self, spec: IntentSpec, new_item: SpecItem
    ) -> list[Conflict]:
        """Detect cost optimization conflicting with high-performance requirements."""
        # Check if new item is high-performance architecture
        high_performance_indicators = {
            "architecture": "multi-region-active-active",
            "scaling": "aggressive",
            "redundancy": "high",
        }

        is_high_perf = (
            new_item.key in high_performance_indicators
            and new_item.value == high_performance_indicators[new_item.key]
        )

        if not is_high_perf:
            return []

        # Check if spec has cost minimization goal
        conflicts = []
        for existing_item in spec.items.values():
            if existing_item.key == "optimization_priority" and "cost" in existing_item.value.lower():
                conflict = Conflict(
                    item_a=existing_item.id,
                    item_b=new_item.id,
                    conflict_type=ConflictType.COST_VS_PERFORMANCE_CONFLICT,
                    description=(
                        f"Cost optimization conflicts with high-performance requirement. "
                        f"{new_item.key}={new_item.value} is expensive."
                    ),
                    resolution_options=[
                        "Prioritize cost (reduce performance requirements)",
                        "Prioritize performance (accept higher cost)",
                        "Find middle ground (balanced approach)",
                    ],
                    auto_resolvable=False,  # Requires user decision
                )
                conflicts.append(conflict)

        return conflicts

    def _check_iac_tool_conflict(
        self, spec: IntentSpec, new_item: SpecItem
    ) -> list[Conflict]:
        """Detect multiple IaC tools specified."""
        if new_item.key != "iac_tool":
            return []

        conflicts = []
        for existing_item in spec.items.values():
            if existing_item.key == "iac_tool" and existing_item.value != new_item.value:
                conflict = Conflict(
                    item_a=existing_item.id,
                    item_b=new_item.id,
                    conflict_type=ConflictType.IAC_TOOL_CONFLICT,
                    description=(
                        f"Multiple IaC tools specified: {existing_item.value} and "
                        f"{new_item.value}. Choose one for consistency."
                    ),
                    resolution_options=[
                        f"Use {existing_item.value}",
                        f"Use {new_item.value}",
                    ],
                    auto_resolvable=self._can_auto_resolve(existing_item, new_item),
                    auto_resolution=self._auto_resolution_message(existing_item, new_item),
                )
                conflicts.append(conflict)

        return conflicts

    def _check_cloud_provider_conflict(
        self, spec: IntentSpec, new_item: SpecItem
    ) -> list[Conflict]:
        """Detect multiple cloud providers."""
        if new_item.key != "cloud_provider":
            return []

        conflicts = []
        for existing_item in spec.items.values():
            if existing_item.key == "cloud_provider" and existing_item.value != new_item.value:
                conflict = Conflict(
                    item_a=existing_item.id,
                    item_b=new_item.id,
                    conflict_type=ConflictType.CLOUD_PROVIDER_CONFLICT,
                    description=(
                        f"Multiple cloud providers: {existing_item.value} and {new_item.value}. "
                        f"Single-cloud or multi-cloud deployment?"
                    ),
                    resolution_options=[
                        f"Deploy to {existing_item.value} only",
                        f"Deploy to {new_item.value} only",
                        "Multi-cloud deployment (more complex)",
                    ],
                    auto_resolvable=self._can_auto_resolve(existing_item, new_item),
                    auto_resolution=self._auto_resolution_message(existing_item, new_item),
                )
                conflicts.append(conflict)

        return conflicts

    def _check_database_conflict(
        self, spec: IntentSpec, new_item: SpecItem
    ) -> list[Conflict]:
        """Detect incompatible database paradigms."""
        if new_item.key != "database":
            return []

        conflicts = []
        for existing_item in spec.items.values():
            if existing_item.key == "database" and existing_item.value != new_item.value:
                new_type = self._get_database_type(new_item.value)
                existing_type = self._get_database_type(existing_item.value)

                if new_type != existing_type and new_type and existing_type:
                    conflict = Conflict(
                        item_a=existing_item.id,
                        item_b=new_item.id,
                        conflict_type=ConflictType.DATABASE_CONFLICT,
                        description=(
                            f"Different database paradigms: {existing_item.value} ({existing_type}) "
                            f"and {new_item.value} ({new_type}). Choose one or use both for different use cases."
                        ),
                        resolution_options=[
                            f"Use {existing_item.value} only",
                            f"Use {new_item.value} only",
                            "Use both for different data types",
                        ],
                        auto_resolvable=self._can_auto_resolve(existing_item, new_item),
                        auto_resolution=self._auto_resolution_message(existing_item, new_item),
                    )
                    conflicts.append(conflict)

        return conflicts

    def _check_environment_conflict(
        self, spec: IntentSpec, new_item: SpecItem
    ) -> list[Conflict]:
        """Detect multiple environment specifications."""
        if new_item.key != "environment":
            return []

        conflicts = []
        for existing_item in spec.items.values():
            if existing_item.key == "environment" and existing_item.value != new_item.value:
                conflict = Conflict(
                    item_a=existing_item.id,
                    item_b=new_item.id,
                    conflict_type=ConflictType.ENVIRONMENT_CONFLICT,
                    description=(
                        f"Multiple environments: {existing_item.value} and {new_item.value}. "
                        f"Generating for one environment or both?"
                    ),
                    resolution_options=[
                        f"Generate for {existing_item.value} only",
                        f"Generate for {new_item.value} only",
                        "Generate separate configs for both",
                    ],
                    auto_resolvable=self._can_auto_resolve(existing_item, new_item),
                    auto_resolution=self._auto_resolution_message(existing_item, new_item),
                )
                conflicts.append(conflict)

        return conflicts

    def _check_security_convenience_conflict(
        self, spec: IntentSpec, new_item: SpecItem
    ) -> list[Conflict]:
        """Detect high security requirements conflicting with public access."""
        is_public_access = new_item.key == "endpoint_visibility" and new_item.value == "public"

        if not is_public_access:
            return []

        conflicts = []
        for existing_item in spec.items.values():
            if existing_item.key == "security_posture" and existing_item.value == "high":
                conflict = Conflict(
                    item_a=existing_item.id,
                    item_b=new_item.id,
                    conflict_type=ConflictType.SECURITY_VS_CONVENIENCE_CONFLICT,
                    description=(
                        "High security posture conflicts with public endpoint access. "
                        "Public endpoints increase attack surface."
                    ),
                    resolution_options=[
                        "Use private endpoints with VPN/bastion access",
                        "Use public endpoints with WAF and rate limiting",
                        "Accept lower security posture for convenience",
                    ],
                    auto_resolvable=False,  # Security decisions require user input
                )
                conflicts.append(conflict)

        return conflicts

    def _get_platform_group(self, platform: str) -> str | None:
        """Get platform group for a compute platform."""
        for group, platforms in self.PLATFORM_GROUPS.items():
            if platform in platforms:
                return group
        return None

    def _get_database_type(self, database: str) -> str | None:
        """Get database type for a database."""
        for db_type, databases in self.DATABASE_TYPES.items():
            if database in databases:
                return db_type
        return None

    def _can_auto_resolve(self, item_a: SpecItem, item_b: SpecItem) -> bool:
        """Check if conflict can be auto-resolved by confidence level."""
        # Auto-resolvable if one item has significantly higher confidence
        confidence_order = [
            ConfidenceBand.SPECULATIVE,
            ConfidenceBand.INFERRED,
            ConfidenceBand.CONFIRMED,
            ConfidenceBand.STATED,
        ]

        a_index = confidence_order.index(item_a.confidence)
        b_index = confidence_order.index(item_b.confidence)

        # Auto-resolvable if difference is 2+ levels
        return abs(a_index - b_index) >= 2

    def _auto_resolution_message(self, item_a: SpecItem, item_b: SpecItem) -> str | None:
        """Generate auto-resolution message if applicable."""
        if not self._can_auto_resolve(item_a, item_b):
            return None

        confidence_order = [
            ConfidenceBand.SPECULATIVE,
            ConfidenceBand.INFERRED,
            ConfidenceBand.CONFIRMED,
            ConfidenceBand.STATED,
        ]

        a_index = confidence_order.index(item_a.confidence)
        b_index = confidence_order.index(item_b.confidence)

        if a_index > b_index:
            return f"Keep {item_a.value} (higher confidence: {item_a.confidence.value})"
        else:
            return f"Keep {item_b.value} (higher confidence: {item_b.confidence.value})"
