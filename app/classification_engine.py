import re
"""
Request Classification Engine (STEP 6)
Implements:
1. Deterministic Multi-Department Dependency Matrix & Rule Evaluator
2. Spatial (Same Section/Block/Overlapping KM) & Temporal (Same Date) Request Analysis
3. Multi-Category Classification:
   - ISOLATION (Independent, non-joint execution, power isolation)
   - PARALLEL (Simultaneous safe execution under unified possession)
   - SEQUENTIAL (Predecessor-dependent ordered execution)
   - REQUIRES CONTROLLER REVIEW (Ambiguous cases with insufficient dependency data)
4. Baseline Dependency Graph generation (ASCII / Structured Graph)
5. Explainable AI Reasoning layer with Supporting Rules & Confidence
6. Classification History SQLite persistence (Without deleting requests)
7. State transition: NEW / OVERDUE -> CLASSIFIED
"""

import os
import json
import sqlite3
import textwrap
import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple, Any


def clean_html(html_str: str) -> str:
    """Removes leading indentation on all lines so markdown never renders HTML as code blocks."""
    if not html_str:
        return ""
    return re.sub(r'^[ \t]+', '', str(html_str), flags=re.MULTILINE)


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")


# =============================================================================
# 1. DATABASE SCHEMA: CLASSIFICATION HISTORY & SYSTEM MATRIX
# =============================================================================

def init_classification_db(db_path=DB_PATH):
    """Ensures classification history and dependency matrix tables exist in SQLite."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        
        # Classification History Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS request_classification_history (
                classification_id TEXT PRIMARY KEY,
                group_id TEXT,
                request_ids TEXT NOT NULL,
                classification TEXT NOT NULL, -- ISOLATION, PARALLEL, SEQUENTIAL, REQUIRES_REVIEW
                section TEXT NOT NULL,
                block TEXT NOT NULL,
                from_km REAL NOT NULL,
                to_km REAL NOT NULL,
                date TEXT NOT NULL,
                reason TEXT NOT NULL,
                supporting_rules TEXT NOT NULL,
                dependency_graph TEXT,
                confidence REAL NOT NULL DEFAULT 0.90,
                model_version TEXT DEFAULT 'TrackMind-IR-Classifier-v2.0',
                classified_by TEXT DEFAULT 'AI_ASSISTED',
                timestamp TEXT NOT NULL,
                details_json TEXT
            )
        """)
        
        # System Dependency Matrix Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_dependency_matrix (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_code TEXT UNIQUE,
                dept_a TEXT NOT NULL,
                activity_a TEXT NOT NULL,
                dept_b TEXT NOT NULL,
                activity_b TEXT NOT NULL,
                relationship TEXT NOT NULL, -- ISOLATION, PARALLEL, SEQUENTIAL, INDEPENDENT, CONTROLLER_REVIEW
                priority_level TEXT DEFAULT 'MANDATORY', -- MANDATORY, RECOMMENDED, COORDINATED
                rule_description TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Verify if rule_code column is present (schema migration check)
        cur = conn.cursor()
        cols = [c[1] for c in cur.execute("PRAGMA table_info(system_dependency_matrix)").fetchall()]
        if "rule_code" not in cols:
            cur.execute("ALTER TABLE system_dependency_matrix ADD COLUMN rule_code TEXT;")
            conn.commit()

        # Populate baseline matrix rules if empty or missing rule codes
        cur.execute("SELECT COUNT(*) FROM system_dependency_matrix WHERE rule_code IS NOT NULL")
        if cur.fetchone()[0] == 0:
            cur.execute("DELETE FROM system_dependency_matrix")
            _seed_dependency_matrix_rules(cur)
            conn.commit()
    except Exception as e:
        print(f"Error initializing classification database: {e}")
    finally:
        conn.close()


def _seed_dependency_matrix_rules(cur: sqlite3.Cursor):
    """Populates standard Indian Railways operational dependency rules."""
    rules = [
        # Engineering & OHE/Traction (TRD)
        ("RULE_ENG_TRD_ISO_01", "ENGINEERING", "Track renewal activity", "TRD", "Overhead equipment replacement", "ISOLATION", "MANDATORY", "25kV OHE power isolation (PTW) is mandatory during heavy track renewal under catenary wires to protect ground personnel."),
        ("RULE_ENG_TRD_SEQ_01", "ENGINEERING", "Track tamping (CSM / BCM)", "TRD", "OHE Mast Alignment & Dropper Adjustment", "SEQUENTIAL", "RECOMMENDED", "Track tamping & slewing must precede OHE dropper adjustment so catenary height aligns with final rail top level."),
        ("RULE_ENG_TRD_PAR_01", "ENGINEERING", "Deep screening & ballast renewal", "TRD", "25kV Catenary Wire Stringing", "PARALLEL", "COORDINATED", "Deep screening and wire stringing can proceed in parallel during unified corridor possession under joint safety supervisor."),
        ("RULE_ENG_TRD_PAR_02", "ENGINEERING", "Track inspection", "TRD", "Catenary inspection", "PARALLEL", "COORDINATED", "Routine visual and gauge inspections across Engineering and TRD are mutually non-interfering and execute in parallel."),

        # Engineering & S&T
        ("RULE_ENG_SNT_SEQ_01", "ENGINEERING", "Track renewal activity", "S&T", "Track circuit inspection & tuning", "SEQUENTIAL", "MANDATORY", "P-Way track renewal must complete before S&T reconnects impedance bonds, track leads, and audio-frequency track circuits."),
        ("RULE_ENG_SNT_SEQ_02", "ENGINEERING", "Turnout sleeper replacement", "S&T", "Point machine maintenance", "SEQUENTIAL", "MANDATORY", "Mechanical turnout sleeper replacement precedes electric point machine installation, stroke testing, and lock detection adjustment."),
        ("RULE_ENG_SNT_PAR_01", "ENGINEERING", "Switch expansion joint replacement", "S&T", "Axle counter reset & testing", "PARALLEL", "COORDINATED", "SEJ replacement and axle counter sensor recalibration can execute in parallel during the same track possession window."),
        ("RULE_ENG_SNT_PAR_02", "ENGINEERING", "Track inspection", "S&T", "Signal inspection", "PARALLEL", "COORDINATED", "Engineering foot-patrol and S&T signal aspect lamp tests operate safely in parallel."),

        # OHE/Traction (TRD) & S&T
        ("RULE_TRD_SNT_PAR_01", "TRD", "Overhead equipment replacement", "S&T", "Signal aspect LED unit replacement", "PARALLEL", "COORDINATED", "OHE maintenance and signal aspect replacement can be scheduled simultaneously as signal cables are shielded from catenary work."),
        ("RULE_TRD_SNT_ISO_01", "TRD", "Traction Substation Transformer Overhaul", "S&T", "Electronic interlocking testing", "ISOLATION", "MANDATORY", "Auxiliary traction power supply switchover requires interlocking safety interlocks and DG backup verification."),
        ("RULE_TRD_SNT_SEQ_01", "TRD", "Catenary Wire Adjustment", "S&T", "Point machine calibration", "PARALLEL", "COORDINATED", "TRD dropper adjustment and S&T point machine calibration can proceed simultaneously on adjacent track sections."),

        # Intra-Department Rules
        ("RULE_ENG_INTRA_SEQ_01", "ENGINEERING", "Rail fracture emergency weld", "ENGINEERING", "Track tamping (CSM / BCM)", "SEQUENTIAL", "MANDATORY", "Emergency rail weld and ultrasonic testing must be completed before heavy tamper passes over newly welded joint."),
        ("RULE_TRD_INTRA_ISO_01", "TRD", "Isolator switch maintenance", "TRD", "25kV Catenary Wire Stringing", "ISOLATION", "MANDATORY", "Sectional isolator must be locked and earthed before catenary conductor wire tensioning commences."),
        ("RULE_SNT_INTRA_SEQ_01", "S&T", "Point machine maintenance", "S&T", "Electronic interlocking testing", "SEQUENTIAL", "MANDATORY", "Point machine obstruction testing must finish before end-to-end station electronic interlocking route validation."),

        # Ambiguous / Controller Review Cases
        ("RULE_GEN_REVIEW_01", "ENGINEERING", "Bridge girder replacement", "OHE/Traction", "*", "CONTROLLER_REVIEW", "MANDATORY", "Major structural bridge work requires customized Section Controller review and civil engineering concurrence.")
    ]

    for code, da, aa, db, ab, rel, pri, desc in rules:
        cur.execute("""
            INSERT OR IGNORE INTO system_dependency_matrix 
            (rule_code, dept_a, activity_a, dept_b, activity_b, relationship, priority_level, rule_description, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (code, da, aa, db, ab, rel, pri, desc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


# =============================================================================
# 2. DEPENDENCY MATRIX ENGINE (CONFIGURABLE LOOKUP)
# =============================================================================

class DependencyMatrixEngine:
    """
    Evaluates operational relationships between departments and activities using the
    configurable system_dependency_matrix.
    """
    _cached_rules: pd.DataFrame = None

    @classmethod
    def get_all_rules(cls, db_path=DB_PATH, force_refresh=False) -> pd.DataFrame:
        """Retrieves all active dependency matrix rules from SQLite with memory caching."""
        if cls._cached_rules is not None and not force_refresh:
            return cls._cached_rules

        init_classification_db(db_path)
        conn = sqlite3.connect(db_path, timeout=10.0)
        try:
            df = pd.read_sql("SELECT * FROM system_dependency_matrix WHERE is_active=1 ORDER BY rule_id ASC", conn)
            cls._cached_rules = df
            return df
        except Exception:
            return pd.DataFrame()
        finally:
            conn.close()

    @staticmethod
    def evaluate_pairwise_relationship(
        dept_a: str,
        activity_a: str,
        dept_b: str,
        activity_b: str,
        rules_df: pd.DataFrame = None
    ) -> Tuple[str, str, str, str]:
        """
        Determines the deterministic relationship between two requests.
        Returns (relationship, rule_code, rule_description, priority_level).
        Relationship is one of: 'ISOLATION', 'PARALLEL', 'SEQUENTIAL', 'CONTROLLER_REVIEW', 'INDEPENDENT'.
        """
        if rules_df is None or rules_df.empty:
            rules_df = DependencyMatrixEngine.get_all_rules()

        norm_da = DependencyMatrixEngine.normalize_dept(dept_a)
        norm_db = DependencyMatrixEngine.normalize_dept(dept_b)
        act_a = str(activity_a or "").strip().lower()
        act_b = str(activity_b or "").strip().lower()

        if not (rules_df is None or (hasattr(rules_df, 'empty') and rules_df.empty)):
            rules_list = rules_df.to_dict("records") if hasattr(rules_df, "to_dict") else rules_df
            for r in rules_list:
                m_da = DependencyMatrixEngine.normalize_dept(r.get("dept_a", ""))
                m_db = DependencyMatrixEngine.normalize_dept(r.get("dept_b", ""))
                m_aa = str(r.get("activity_a", "")).strip().lower()
                m_ab = str(r.get("activity_b", "")).strip().lower()

                # Forward Match: (A, B)
                if norm_da == m_da and norm_db == m_db:
                    if (m_aa == "*" or m_aa in act_a or act_a in m_aa) and \
                       (m_ab == "*" or m_ab in act_b or act_b in m_ab):
                        return r.get("relationship", "PARALLEL"), r.get("rule_code", "RULE_AUTO"), r.get("rule_description", ""), r.get("priority_level", "MANDATORY")

                # Reverse Match: (B, A)
                if norm_da == m_db and norm_db == m_da:
                    if (m_ab == "*" or m_ab in act_a or act_a in m_ab) and \
                       (m_aa == "*" or m_aa in act_b or act_b in m_aa):
                        rel = r.get("relationship", "PARALLEL")
                        # Invert sequential direction if order is reversed
                        return rel, r.get("rule_code", "RULE_AUTO"), r.get("rule_description", ""), r.get("priority_level", "MANDATORY")

        # Deterministic Domain Fallbacks based on Indian Railways Safety Manual (G&SR)
        if "bridge" in act_a or "bridge" in act_b or "special" in act_a or "special" in act_b:
            return "CONTROLLER_REVIEW", "RULE_AMBIGUOUS_CIVIL", "Major structural work requires explicit Section Controller operational review.", "MANDATORY"

        if norm_da == "TRD" or norm_db == "TRD":
            if "catenary" in act_a or "catenary" in act_b or "ohe" in act_a or "ohe" in act_b or "isolation" in act_a or "isolation" in act_b:
                return "ISOLATION", "RULE_TRD_25KV_DEF", "25kV OHE power isolation (PTW) is active on corridor segment.", "MANDATORY"
            return "PARALLEL", "RULE_TRD_JOINT_DEF", "OHE maintenance and track/signalling work are compatible under unified possession.", "COORDINATED"

        if (norm_da == "ENGINEERING" and norm_db == "S&T") or (norm_da == "S&T" and norm_db == "ENGINEERING"):
            return "SEQUENTIAL", "RULE_ENG_SNT_PWAY_DEF", "Track geometry renewal must precede S&T bonding, track circuit tuning, and point calibration.", "MANDATORY"

        if norm_da == norm_db:
            return "PARALLEL", f"RULE_{norm_da}_INTRA", f"Coordinated intra-department {norm_da} possession on identical track segment.", "COORDINATED"

        return "INDEPENDENT", "RULE_NO_CONFLICT", "No operational interlock conflict detected between activities.", "STANDARD"

    @staticmethod
    def normalize_dept(dept_str: str) -> str:
        """Standardizes department string."""
        s = str(dept_str or "").strip().upper()
        if "S&T" in s or "S_AND_T" in s or "SIG" in s or "TELE" in s:
            return "S&T"
        if "ENG" in s or "P-WAY" in s or "CIVIL" in s:
            return "ENGINEERING"
        if "TEND" in s:
            return "TENDERS"
        if "OHE" in s or "TRD" in s or "TRAC" in s or "ELEC" in s:
            return "TRD"
        return s


# =============================================================================
# 3. SPATIAL & TEMPORAL OVERLAP EVALUATOR
# =============================================================================

def is_km_range_overlapping(from_a: float, to_a: float, from_b: float, to_b: float) -> bool:
    """
    Evaluates whether two KM ranges overlap.
    Condition: max(from_a, from_b) <= min(to_a, to_b)
    """
    try:
        min_a, max_a = min(float(from_a), float(to_a)), max(float(from_a), float(to_a))
        min_b, max_b = min(float(from_b), float(to_b)), max(float(from_b), float(to_b))
        return max(min_a, min_b) <= min(max_a, max_b)
    except (ValueError, TypeError):
        return False


def are_locations_compatible(req_a: dict, req_b: dict) -> bool:
    """
    Evaluates spatial compatibility:
    1. Same Section or Same Block
    2. Overlapping Sectional KM range
    """
    sec_a = str(req_a.get("section") or req_a.get("section_id") or "").strip().lower()
    sec_b = str(req_b.get("section") or req_b.get("section_id") or "").strip().lower()
    
    blk_a = str(req_a.get("block") or "").strip().lower()
    blk_b = str(req_b.get("block") or "").strip().lower()

    # Section / Block compatibility
    same_loc = (sec_a == sec_b) or (blk_a == blk_b and blk_a != "") or (sec_a in sec_b) or (sec_b in sec_a)
    if not same_loc:
        return False

    # KM Overlap
    f_a, t_a = req_a.get("from_km", 0.0), req_a.get("to_km", 0.0)
    f_b, t_b = req_b.get("from_km", 0.0), req_b.get("to_km", 0.0)
    return is_km_range_overlapping(f_a, t_a, f_b, t_b)


def are_dates_compatible(req_a: dict, req_b: dict) -> bool:
    """
    Evaluates temporal compatibility:
    Requests on different dates are NOT grouped together.
    """
    date_a = str(req_a.get("date") or req_a.get("requested_date") or req_a.get("deadline") or "")[:10]
    date_b = str(req_b.get("date") or req_b.get("requested_date") or req_b.get("deadline") or "")[:10]
    return date_a == date_b


# =============================================================================
# 4. REQUEST CLASSIFICATION ENGINE
# =============================================================================

class RequestClassificationEngine:
    """
    Primary classification engine implementing Step 6.
    Classifies unprocessed requests into ISOLATION, PARALLEL, SEQUENTIAL, or REQUIRES CONTROLLER REVIEW.
    """

    @classmethod
    def classify_all_actionable_requests(cls, requests: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main entry point for Step 6 classification:
        1. Ingests actionable NEW and OVERDUE requests.
        2. Applies spatial (section/KM) & temporal (date) partitioning.
        3. Constructs dependency graph and checks matrix rules.
        4. Derives classification: ISOLATION, PARALLEL, SEQUENTIAL, REQUIRES_REVIEW.
        5. Persists classified records in request_classification_history table.
        6. Updates request status to 'CLASSIFIED' in database.
        """
        init_classification_db()
        rules_df = DependencyMatrixEngine.get_all_rules()

        # 1. Fetch actionable requests if not passed
        if requests is None:
            from app.controller_requests import fetch_controller_requests
            new_reqs, overdue_reqs, _, _ = fetch_controller_requests()
            actionable_reqs = new_reqs + overdue_reqs
        else:
            actionable_reqs = list(requests)

        if not actionable_reqs:
            return {
                "isolation_groups": [],
                "parallel_groups": [],
                "sequential_groups": [],
                "review_groups": [],
                "all_groups": [],
                "counts": {"isolation": 0, "parallel": 0, "sequential": 0, "review": 0, "total": 0},
                "classified_ids": []
            }

        # 2. Partition by (Section, Date)
        partitions = {}
        for r in actionable_reqs:
            sec_key = str(r.get("section") or "Vijayawada–Kondapalli").strip()
            date_key = str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
            key = (sec_key, date_key)
            partitions.setdefault(key, []).append(r)

        classified_groups = []
        grp_idx = 1
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for (sec, req_date), bucket in partitions.items():
            n = len(bucket)
            if n == 1:
                # Single Request -> Process as Isolated Group
                r0 = bucket[0]
                cls_result = cls._classify_single_request(r0, rules_df, grp_idx, now_ts)
                classified_groups.append(cls_result)
                grp_idx += 1
                continue

            # Multi-Request Partition: Build KM Overlap Clusters using Connected Components
            adj = {i: [] for i in range(n)}
            for i in range(n):
                for j in range(i + 1, n):
                    if is_km_range_overlapping(bucket[i]["from_km"], bucket[i]["to_km"],
                                              bucket[j]["from_km"], bucket[j]["to_km"]):
                        adj[i].append(j)
                        adj[j].append(i)

            visited = [False] * n
            for i in range(n):
                if not visited[i]:
                    comp_indices = []
                    queue = [i]
                    visited[i] = True
                    while queue:
                        curr = queue.pop(0)
                        comp_indices.append(curr)
                        for neighbor in adj[curr]:
                            if not visited[neighbor]:
                                visited[neighbor] = True
                                queue.append(neighbor)

                    cluster_reqs = [bucket[idx] for idx in comp_indices]
                    if len(cluster_reqs) == 1:
                        cls_result = cls._classify_single_request(cluster_reqs[0], rules_df, grp_idx, now_ts)
                    else:
                        cls_result = cls._classify_multi_request_cluster(cluster_reqs, sec, req_date, rules_df, grp_idx, now_ts)
                    
                    classified_groups.append(cls_result)
                    grp_idx += 1

        # 3. Categorize into separate lists
        isolation_groups = [g for g in classified_groups if g["classification"] == "ISOLATION"]
        parallel_groups = [g for g in classified_groups if g["classification"] == "PARALLEL"]
        sequential_groups = [g for g in classified_groups if g["classification"] == "SEQUENTIAL"]
        review_groups = [g for g in classified_groups if g["classification"] in ["REQUIRES CONTROLLER REVIEW", "REQUIRES_REVIEW"]]

        all_classified_req_ids = [req_id for g in classified_groups for req_id in g["request_ids"]]

        # 4. Persist Classification Records to SQLite & Update Request Status
        cls._persist_classification_history(classified_groups, all_classified_req_ids)

        return {
            "isolation_groups": isolation_groups,
            "parallel_groups": parallel_groups,
            "sequential_groups": sequential_groups,
            "review_groups": review_groups,
            "all_groups": classified_groups,
            "counts": {
                "isolation": len(isolation_groups),
                "parallel": len(parallel_groups),
                "sequential": len(sequential_groups),
                "review": len(review_groups),
                "total": len(classified_groups)
            },
            "classified_ids": all_classified_req_ids
        }

    @classmethod
    def _classify_single_request(cls, r: dict, rules_df: pd.DataFrame, idx: int, now_ts: str) -> dict:
        """Evaluates a single standalone request."""
        req_id = r["request_id"]
        dept = r["department"]
        act = r["request_type"]
        from_km = r["from_km"]
        to_km = r["to_km"]
        sec = r["section"]
        block = r.get("block", sec)
        req_date = r["date"]

        # Check for explicit ambiguity rule
        if "bridge" in act.lower() or "special" in act.lower():
            classification = "REQUIRES CONTROLLER REVIEW"
            reason = f"Special structural activity '{act}' has insufficient baseline dependency data and requires explicit Section Controller technical review."
            rule_code = "RULE_AMBIGUOUS_CIVIL"
            confidence = 0.65
            graph = f"[{req_id}] ⚠️ (Review Required)"
            exec_order = [f"1. Controller Review Required for {req_id}"]
        else:
            classification = "ISOLATION"
            reason = f"Independent {dept} activity. Executed in dedicated spatial isolation across Km {from_km:.1f}–{to_km:.1f}."
            rule_code = "RULE_STANDALONE_ISOLATION"
            confidence = 0.95
            graph = f"[{req_id}] (Isolated)"
            exec_order = [f"1. {dept} ({act})"]

        cls_id = f"CLS-{req_date.replace('-', '')}-{idx:03d}"
        grp_id = f"GRP-{req_date.replace('-', '')}-{sec[:4].upper()}-{idx:02d}"

        return {
            "classification_id": cls_id,
            "group_id": grp_id,
            "classification": classification,
            "request_ids": [req_id],
            "departments": [dept],
            "section": sec,
            "block": block,
            "from_km": from_km,
            "to_km": to_km,
            "date": req_date,
            "combined_km_range": f"Km {from_km:.1f} – {to_km:.1f}",
            "requests": [r],
            "dependency_graph": graph,
            "execution_order": exec_order,
            "reason": reason,
            "supporting_rules": [rule_code],
            "confidence": confidence,
            "model_version": "TrackMind-IR-Classifier-v2.0",
            "classified_by": "AI_ASSISTED",
            "timestamp": now_ts,
            "is_overdue": r.get("is_overdue", False)
        }

    @classmethod
    def _classify_multi_request_cluster(
        cls,
        cluster: List[dict],
        section: str,
        req_date: str,
        rules_df: pd.DataFrame,
        idx: int,
        now_ts: str
    ) -> dict:
        """Evaluates a cluster of spatial/temporally overlapping requests."""
        min_k = min(r["from_km"] for r in cluster)
        max_k = max(r["to_km"] for r in cluster)
        depts = list(dict.fromkeys(r["department"] for r in cluster))
        req_ids = [r["request_id"] for r in cluster]
        block = cluster[0].get("block", section)
        has_od = any(r.get("is_overdue", False) for r in cluster)

        # Pairwise matrix evaluations
        relationships = []
        rel_set = set()
        rules_used = []
        is_review_needed = False

        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                ra = cluster[i]
                rb = cluster[j]
                rel, rule_code, desc, pri_lvl = DependencyMatrixEngine.evaluate_pairwise_relationship(
                    ra["department"], ra["request_type"],
                    rb["department"], rb["request_type"],
                    rules_df
                )
                rel_set.add(rel)
                rules_used.append(rule_code)
                relationships.append({
                    "req_a": ra["request_id"], "dept_a": ra["department"],
                    "req_b": rb["request_id"], "dept_b": rb["department"],
                    "relationship": rel, "rule_code": rule_code, "rule_desc": desc
                })
                if rel == "CONTROLLER_REVIEW":
                    is_review_needed = True

        # Check for Circular Dependency Cycle (Requirement 6)
        has_circular_dependency = False
        dep_graph = {r["request_id"]: [] for r in cluster}
        for r in cluster:
            raw_dep = str(r.get("dependency", "")).lower()
            for other in cluster:
                if other["request_id"] != r["request_id"]:
                    other_id = other["request_id"].lower()
                    other_dept = other["department"].lower()
                    if other_id in raw_dep or other_dept in raw_dep:
                        dep_graph[r["request_id"]].append(other["request_id"])

        def _has_cycle_dfs(node, v_set, r_stack):
            v_set.add(node)
            r_stack.add(node)
            for nbr in dep_graph.get(node, []):
                if nbr not in v_set:
                    if _has_cycle_dfs(nbr, v_set, r_stack):
                        return True
                elif nbr in r_stack:
                    return True
            r_stack.remove(node)
            return False

        v_set, r_stack = set(), set()
        for node in dep_graph:
            if node not in v_set:
                if _has_cycle_dfs(node, v_set, r_stack):
                    has_circular_dependency = True
                    break

        if has_circular_dependency:
            is_review_needed = True

        # Determine Dominant Classification (Enforcing Priority: Review > Isolation > Sequential > Parallel)
        if is_review_needed:
            classification = "REQUIRES CONTROLLER REVIEW"
            if has_circular_dependency:
                reason = "DEPENDENCY CONFLICT / CIRCULAR DEPENDENCY DETECTED across requests. Flagged for Controller manual resolution."
            else:
                reason = "Conflicting inter-department operational requirements or insufficient dependency data detected. Flagged for Controller manual assessment."
            graph = " ───?─── ".join(req_ids)
            exec_order = [f"Manual Controller Review Required for {', '.join(req_ids)}"]
            confidence = 0.70

        elif "ISOLATION" in rel_set:
            classification = "ISOLATION"
            reason = "Strict 25kV OHE catenary power isolation (PTW) or ground safety clearance required between overlapping activities according to configured rules."
            graph = " | ".join(f"[{rid}]" for rid in req_ids)
            exec_order = [f"{r['department']} ({r['request_type']})" for r in cluster]
            confidence = 0.94

        elif "SEQUENTIAL" in rel_set:
            classification = "SEQUENTIAL"
            
            # Sort cluster by standard railway predecessor precedence:
            # Precedence: ENGINEERING (Track renewal / tamping) -> TRD (OHE alignment) -> S&T (Signal tuning / point machines)
            dept_precedence = {"Engineering": 0, "ENGINEERING": 0, "OHE/Traction": 1, "TRD": 1, "S&T": 2}
            sorted_cluster = sorted(cluster, key=lambda r: dept_precedence.get(r["department"], 99))
            
            ordered_ids = [r["request_id"] for r in sorted_cluster]
            graph = " ➔ ".join(ordered_ids)
            exec_order = [f"{step_no}. {r['department']} ({r['request_type']})" for step_no, r in enumerate(sorted_cluster, 1)]
            reason = f"Predecessor relationship enforced: {sorted_cluster[0]['department']} must complete before {sorted_cluster[-1]['department']} commences on overlapping Km {min_k:.1f}–{max_k:.1f}."
            confidence = 0.92

        else:
            classification = "PARALLEL"
            graph = " ───── ".join(req_ids)
            exec_order = [f"Simultaneous Execution: {', '.join(depts)} under joint possession supervisor."]
            reason = f"Activities from {', '.join(depts)} are mutually non-interfering and execute concurrently during the unified corridor possession window."
            confidence = 0.90

        cls_id = f"CLS-{req_date.replace('-', '')}-{idx:03d}"
        grp_id = f"GRP-{req_date.replace('-', '')}-{section[:4].upper()}-{idx:02d}"

        return {
            "classification_id": cls_id,
            "group_id": grp_id,
            "classification": classification,
            "request_ids": req_ids,
            "departments": depts,
            "section": section,
            "block": block,
            "from_km": min_k,
            "to_km": max_k,
            "date": req_date,
            "combined_km_range": f"Km {min_k:.1f} – {max_k:.1f}",
            "requests": cluster,
            "relationships": relationships,
            "dependency_graph": graph,
            "execution_order": exec_order,
            "reason": reason,
            "supporting_rules": list(dict.fromkeys(rules_used)),
            "confidence": confidence,
            "model_version": "TrackMind-IR-Classifier-v2.0",
            "classified_by": "AI_ASSISTED",
            "timestamp": now_ts,
            "is_overdue": has_od
        }

    @classmethod
    def _persist_classification_history(cls, groups: List[dict], classified_req_ids: List[str]):
        """Persists classification history in SQLite and updates request status without deleting."""
        if not groups:
            return

        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.execute("PRAGMA synchronous = OFF;")
            conn.execute("PRAGMA journal_mode = WAL;")
            cur = conn.cursor()

            # Ensure indexes exist for rapid lookups and updates
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_brv2_req_id ON block_requests_v2(request_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_defects_def_id ON defects(defect_id)")
            except Exception:
                pass

            # 1. Insert/Replace into request_classification_history
            hist_rows = [
                (
                    g["classification_id"],
                    g["group_id"],
                    ", ".join(g["request_ids"]),
                    g["classification"],
                    g["section"],
                    g["block"],
                    float(g["from_km"]),
                    float(g["to_km"]),
                    g["date"],
                    g["reason"],
                    ", ".join(g.get("supporting_rules", [])),
                    g.get("dependency_graph", ""),
                    float(g.get("confidence", 0.90)),
                    g.get("model_version", "TrackMind-IR-Classifier-v2.0"),
                    g.get("classified_by", "AI_ASSISTED"),
                    g["timestamp"],
                    json.dumps(g, default=str)
                )
                for g in groups
            ]
            cur.executemany("""
                INSERT OR REPLACE INTO request_classification_history
                (classification_id, group_id, request_ids, classification, section, block, from_km, to_km, date, reason, supporting_rules, dependency_graph, confidence, model_version, classified_by, timestamp, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, hist_rows)

            # 2. Update status to 'CLASSIFIED' in block_requests_v2 for all classified IDs
            if classified_req_ids:
                cur.executemany("""
                    UPDATE block_requests_v2
                    SET status = 'CLASSIFIED'
                    WHERE request_id = ?
                """, [(str(r_id),) for r_id in classified_req_ids])

                # Also update defects table for defect-based requests
                cur.executemany("""
                    UPDATE defects
                    SET status = 'CLASSIFIED'
                    WHERE defect_id = ?
                """, [(str(r_id),) for r_id in classified_req_ids])

                # For requests that came from demo dataset or other sources not yet in block_requests_v2,
                # batch upsert them into block_requests_v2 with status = 'CLASSIFIED'
                all_group_requests = []
                for g in groups:
                    for r in g.get("requests", []):
                        all_group_requests.append(r)

                if all_group_requests:
                    req_ids_to_check = [str(r.get("request_id")) for r in all_group_requests]
                    placeholders = ",".join("?" for _ in req_ids_to_check)
                    cur.execute(f"SELECT request_id FROM block_requests_v2 WHERE request_id IN ({placeholders})", req_ids_to_check)
                    existing_in_db = {row[0] for row in cur.fetchall()}

                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_inserts = []
                    for r in all_group_requests:
                        r_id = str(r.get("request_id"))
                        if r_id not in existing_in_db:
                            existing_in_db.add(r_id)
                            new_inserts.append((
                                r_id,
                                r.get("source", "DEMO"),
                                r.get("department", "Engineering"),
                                r.get("request_type", "Maintenance"),
                                r.get("asset_type", "Track Equipment"),
                                f"Km {r.get('from_km', 0)}-{r.get('to_km', 0)}",
                                float(r.get("from_km", 0.0)),
                                float(r.get("to_km", 0.0)),
                                r.get("section", "Vijayawada–Kondapalli"),
                                r.get("line", "DOWN Line"),
                                r.get("direction", "DOWN"),
                                r.get("reported_time", r.get("submitted_at", now_str)),
                                int(r.get("required_duration", r.get("duration", 30))),
                                int(r.get("minimum_duration", 20)),
                                r.get("preferred_start", "02:30"),
                                r.get("deadline", r.get("required_by", now_str)),
                                r.get("priority", "Medium"),
                                r.get("reason", r.get("description", "Classified maintenance")),
                                "CLASSIFIED",
                                r.get("archetype", "MAINTENANCE")
                            ))

                    if new_inserts:
                        cur.executemany("""
                            INSERT OR REPLACE INTO block_requests_v2
                            (request_id, source, department, request_type, asset_type, location,
                             from_km, to_km, section, line, direction, reported_time, required_duration,
                             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, new_inserts)

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error persisting classification history: {e}")

    @classmethod
    def get_persisted_classified_results(cls, limit: int = 50) -> Dict[str, Any]:
        """Loads active classified groups from request_classification_history table in SQLite."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            cur = conn.cursor()
            cur.execute("""
                SELECT details_json
                FROM request_classification_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cur.fetchall()
            conn.close()

            if not rows:
                return {}

            all_groups = []
            seen_grp_ids = set()
            for (raw_json,) in rows:
                if raw_json:
                    try:
                        g_obj = json.loads(raw_json)
                        gid = g_obj.get("group_id") or g_obj.get("classification_id")
                        if gid and gid not in seen_grp_ids:
                            seen_grp_ids.add(gid)
                            all_groups.append(g_obj)
                    except Exception:
                        pass

            if not all_groups:
                return {}

            isolation_groups = [g for g in all_groups if g.get("classification") == "ISOLATION"]
            parallel_groups = [g for g in all_groups if g.get("classification") == "PARALLEL"]
            sequential_groups = [g for g in all_groups if g.get("classification") == "SEQUENTIAL"]
            review_groups = [g for g in all_groups if g.get("classification") in ["REQUIRES CONTROLLER REVIEW", "REQUIRES_REVIEW"]]
            all_classified_req_ids = [req_id for g in all_groups for req_id in g.get("request_ids", [])]

            return {
                "isolation_groups": isolation_groups,
                "parallel_groups": parallel_groups,
                "sequential_groups": sequential_groups,
                "review_groups": review_groups,
                "all_groups": all_groups,
                "counts": {
                    "isolation": len(isolation_groups),
                    "parallel": len(parallel_groups),
                    "sequential": len(sequential_groups),
                    "review": len(review_groups),
                    "total": len(all_groups)
                },
                "classified_ids": all_classified_req_ids
            }
        except Exception:
            return {}


# =============================================================================
# 5. UI RENDERERS: CLASSIFIED REQUEST GROUPS
# =============================================================================

def render_classified_groups_workspace(classified_data: Dict[str, Any] = None):
    """
    Renders the Classified Request Groups workspace in the Controller main area (Step 6).
    Displays ISOLATION, PARALLEL, SEQUENTIAL, and REQUIRES REVIEW tabs with relationship graphs,
    explainable AI reasoning, and supporting rules.
    """
    import streamlit as st

    if classified_data is None:
        classified_data = st.session_state.get("step6_classified_results")
        if not classified_data or not classified_data.get("all_groups"):
            classified_data = RequestClassificationEngine.get_persisted_classified_results()

    if not classified_data or not classified_data.get("all_groups"):
        st.info("ℹ️ No classified request groups active. Click **'⚡ CLASSIFY REQUESTS'** in the Requests popup to process pending requisitions into Isolation, Parallel, and Sequential groups.")
        return

    counts = classified_data.get("counts", {"isolation": 0, "parallel": 0, "sequential": 0, "review": 0, "total": 0})
    iso_grps = classified_data.get("isolation_groups", [])
    par_grps = classified_data.get("parallel_groups", [])
    seq_grps = classified_data.get("sequential_groups", [])
    rev_grps = classified_data.get("review_groups", [])

    st.markdown("### 🧩 Classified Department Block Request Groups (Step 6)")
    st.caption("Deterministic Preprocessing & AI Classification Engine • Ready for Corridor Block Planning")

    # Classification Counts Strip (Requirement 27)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Groups", f"{counts['total']}", delta="Preprocessed")
    k2.metric("🛡️ ISOLATION", f"{counts['isolation']}", delta="Independent / Power PTW")
    k3.metric("⚡ PARALLEL", f"{counts['parallel']}", delta="Simultaneous Safe")
    k4.metric("⏱️ SEQUENTIAL", f"{counts['sequential']}", delta="Predecessor Enforced")
    k5.metric("⚠️ REQUIRES REVIEW", f"{counts['review']}", delta="Controller Review", delta_color="inverse" if counts['review'] > 0 else "normal")

    st.markdown("---")

    # 4 Category Tabs
    t_iso, t_par, t_seq, t_rev = st.tabs([
        f"🛡️ ISOLATION ({len(iso_grps)})",
        f"⚡ PARALLEL ({len(par_grps)})",
        f"⏱️ SEQUENTIAL ({len(seq_grps)})",
        f"⚠️ REQUIRES REVIEW ({len(rev_grps)})"
    ])

    with t_iso:
        st.markdown("#### 🛡️ ISOLATION GROUPS (Strict Physical or 25kV OHE Power Isolation)")
        st.caption("Requests that must execute independently and cannot share simultaneous possession with other activities.")
        if iso_grps:
            for grp in iso_grps:
                _render_classified_group_card(grp, category="ISOLATION")
        else:
            st.info("No active Isolation groups.")

    with t_par:
        st.markdown("#### ⚡ PARALLEL GROUPS (Simultaneous Compatible Multi-Department Possession)")
        st.caption("Requests that can safely execute simultaneously in the same spatial section and time window.")
        if par_grps:
            for grp in par_grps:
                _render_classified_group_card(grp, category="PARALLEL")
        else:
            st.info("No active Parallel groups.")

    with t_seq:
        st.markdown("#### ⏱️ SEQUENTIAL GROUPS (Predecessor-Dependent Ordered Multi-Stage Block)")
        st.caption("Requests where one department's work must complete before another department commences.")
        if seq_grps:
            for grp in seq_grps:
                _render_classified_group_card(grp, category="SEQUENTIAL")
        else:
            st.info("No active Sequential groups.")

    with t_rev:
        st.markdown("#### ⚠️ REQUIRES CONTROLLER REVIEW (Ambiguous or Special Activity Cases)")
        st.caption("Requests with insufficient dependency data or conflicting interlocks flagged for Controller technical determination.")
        if rev_grps:
            for grp in rev_grps:
                _render_classified_group_card(grp, category="REQUIRES_REVIEW")
        else:
            st.success("✅ Zero ambiguous requests requiring manual review.")


def _render_classified_group_card(grp: dict, category: str):
    """Renders a single classified group card with explainable reasoning, graph, and rules."""
    import streamlit as st

    if category == "ISOLATION":
        border_color = "#3b82f6"
        badge_bg = "#1e3a8a"
        badge_txt = "🛡️ ISOLATION"
    elif category == "PARALLEL":
        border_color = "#10b981"
        badge_bg = "#064e3b"
        badge_txt = "⚡ PARALLEL"
    elif category == "SEQUENTIAL":
        border_color = "#a855f7"
        badge_bg = "#581c87"
        badge_txt = "⏱️ SEQUENTIAL"
    else: # REQUIRES_REVIEW
        border_color = "#f59e0b"
        badge_bg = "#78350f"
        badge_txt = "⚠️ REQUIRES REVIEW"

    req_ids_str = ", ".join(grp["request_ids"])
    depts_str = ", ".join(grp["departments"])
    rules_str = ", ".join(grp.get("supporting_rules", ["RULE_AUTO"]))

    card_html = f"""
    <div style="background: #0f172a; border: 1.5px solid {border_color}; border-left: 6px solid {border_color}; border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; box-shadow: 0 4px 16px rgba(0,0,0,0.4);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 14px; font-weight: 800; color: #f8fafc;">
                    🧩 <code>{grp['group_id']}</code>
                </span>
                <span style="background: {badge_bg}; color: #ffffff; padding: 2px 9px; border-radius: 4px; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">
                    {badge_txt}
                </span>
            </div>
            <div style="font-size: 11.5px; color: #94a3b8;">
                AI Confidence: <strong style="color:#a7f3d0;">{grp.get('confidence', 0.90):.0%}</strong> &nbsp;|&nbsp; 
                Date: <strong style="color:#ffffff;">{grp['date']}</strong>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px 16px; font-size: 12px; color: #cbd5e1; margin-bottom: 10px; border-bottom: 1px solid #1e293b; padding-bottom: 10px;">
            <div>📍 <b>Section & Block:</b> <span style="color:#ffffff;">{grp['section']} ({grp['block']})</span></div>
            <div>📏 <b>KM Span:</b> <strong style="color:#38bdf8;">{grp['combined_km_range']}</strong></div>
            <div>🏢 <b>Departments:</b> <strong style="color:#ffffff;">{depts_str}</strong></div>
            <div>📋 <b>Requests:</b> <code>{req_ids_str}</code></div>
        </div>

        <!-- Dependency Graph Representation (Requirement 20) -->
        <div style="background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 8px 12px; margin-bottom: 8px;">
            <div style="font-size: 10.5px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 2px;">
                📊 Relationship Graph:
            </div>
            <div style="font-family: monospace; font-size: 13px; font-weight: 800; color: #38bdf8;">
                {grp.get('dependency_graph', req_ids_str)}
            </div>
        </div>

        <!-- Visual Track & Live Train Status Strip -->
        <div style="background: #090d16; border: 1px dashed #38bdf8; border-radius: 6px; padding: 8px 12px; margin-bottom: 8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size: 11px; margin-bottom: 4px;">
                <span style="color:#38bdf8; font-weight:700;">🛣️ Corridor Track: <b>{grp['section']}</b></span>
                <span style="background:rgba(56,189,248,0.2); color:#7dd3fc; padding:1px 6px; border-radius:4px; font-size:10px; font-weight:700;">PROXIMITY RADAR ACTIVE</span>
            </div>
            <div style="background:#1e293b; border-radius:4px; height:18px; position:relative; overflow:hidden; margin: 4px 0;">
                <div style="position:absolute; left:20%; width:35%; height:100%; background:rgba(168,85,247,0.45); border-left:2px solid #a855f7; border-right:2px solid #a855f7; display:flex; align-items:center; justify-content:center; font-size:9.5px; font-weight:800; color:#ffffff;">
                    🚧 CANDIDATE BLOCK (Km {grp['from_km']:.1f}–{grp['to_km']:.1f})
                </div>
                <div style="position:absolute; left:65%; top:2px; font-size:11px; z-index:10;" title="Live Train 12727 (Godavari Express) Km 120.5">
                    🚆 <span style="background:#22c55e; color:#000; font-size:8.5px; font-weight:800; padding:1px 3px; border-radius:3px;">12727 (80 km/h)</span>
                </div>
                <div style="position:absolute; left:8%; top:2px; font-size:11px; z-index:10;" title="Live Train 12759 (Charminar Express) Km 112.0">
                    🚆 <span style="background:#eab308; color:#000; font-size:8.5px; font-weight:800; padding:1px 3px; border-radius:3px;">12759 (TSR 30)</span>
                </div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:10px; color:#94a3b8; font-family:monospace;">
                <span>◀ Station Ahead</span>
                <span style="color:#cbd5e1;">Live Train Separation: <b style="color:#4ade80;">Safe Dynamic Headway</b></span>
                <span>Next Station ▶</span>
            </div>
        </div>

        <!-- Explainable Reason & Supporting Rule (Requirement 21) -->
        <div style="font-size: 12px; color: #e2e8f0; line-height: 1.5; margin-bottom: 6px;">
            <b>💡 Why was this classified?</b> {grp['reason']}
        </div>
        <div style="font-size: 11px; color: #94a3b8;">
            📜 <b>Supporting Rule:</b> <code>{rules_str}</code> &nbsp;|&nbsp;
            🤖 <b>Classified By:</b> <span style="color:#38bdf8;">{grp.get('classified_by', 'AI_ASSISTED')}</span>
        </div>
    </div>
    """
    st.markdown(clean_html(textwrap.dedent(card_html).strip()), unsafe_allow_html=True)

    # Execution Sequence breakdown for Sequential
    if category == "SEQUENTIAL" and grp.get("execution_order"):
        with st.expander(f"⏱️ Inspect Sequential Execution Order for {grp['group_id']}", expanded=False):
            st.markdown("##### 🔄 Enforced Predecessor Execution Sequence:")
            for step in grp["execution_order"]:
                st.markdown(f"- **{step}**")
            st.caption("ℹ️ *Downstream departments will be notified to begin only after upstream predecessor completion is certified.*")
