import os
import json
import re
import logging
try:
    from backend.services.career_context_service import fetch_user_career_data
except ImportError:
    from services.career_context_service import fetch_user_career_data

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

# Ensure environment variables are loaded from backend/.env or root .env
_backend_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)
else:
    load_dotenv()

from services.resume_intelligence import call_gemini_with_retry, clean_json_text

# Official Google GenAI SDK (google-genai)
try:
    from google import genai
except ImportError:
    genai = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_configured = bool(
    GEMINI_API_KEY 
    and not GEMINI_API_KEY.startswith("your-") 
    and not GEMINI_API_KEY.startswith("dummy") 
    and GEMINI_API_KEY != "your_gemini_api_key_here"
)

genai_client = None

if is_gemini_configured and genai is not None:
    try:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Career Roadmap Service: Official google.genai client initialized.")
    except Exception as client_err:
        logger.warning(f"Career Roadmap Service: google.genai client initialization failed: {client_err}")
elif not is_gemini_configured:
    logger.warning("Career Roadmap Service: GEMINI_API_KEY is not configured or is placeholder.")


def get_readiness_label(score):
    """Computes readiness label based on numerical score (0-100)."""
    if score >= 90:
        return "Highly Ready"
    elif score >= 75:
        return "Strongly Prepared"
    elif score >= 60:
        return "Developing"
    elif score >= 40:
        return "Needs Improvement"
    else:
        return "Early Stage"


def generate_career_roadmap(uid, career_goal=""):
    """
    Generates a dynamic personalized career roadmap and learning plan
    based on the candidate's actual CareerPilot profile data (Career Goal, Profile, Resumes, ATS, Job Matches, Skill Gaps, Interview Feedback).
    """
    # 1. Retrieve all user career context
    user_data = fetch_user_career_data(uid)

    goal_obj = user_data.get("career_goal") or {}
    profile_obj = user_data.get("profile") or {}
    resumes = user_data.get("resumes") or []
    job_matches = user_data.get("job_matches") or []
    analyses = user_data.get("analyses") or []
    ats_scores = user_data.get("ats_scores") or []
    interviews = user_data.get("interviews") or []

    # Target company and role determination
    target_company = (goal_obj.get("company_name") or "").strip()
    target_role = (goal_obj.get("job_role") or "").strip()

    if not target_role:
        if career_goal and career_goal.strip():
            target_role = career_goal.strip()
        elif job_matches:
            target_role = job_matches[0].get("job_title") or "Software Engineer"
        else:
            target_role = "Software Engineer"

    if not target_company:
        target_company = "Target Tech Company"

    # Profile & Education Details
    edu = profile_obj.get("education") or {}
    edu_text = f"Education: {edu.get('highest_education', '')} in {edu.get('specialization', '')} from {edu.get('institution', '')}" if edu else "Education: Not specified"

    skills_dict = profile_obj.get("skills") or {}
    curr_prog_langs = skills_dict.get("programming_languages") or []
    curr_tech_skills = skills_dict.get("technical_skills") or []
    curr_tools = skills_dict.get("tools_and_technologies") or []
    curr_soft_skills = skills_dict.get("soft_skills") or []
    
    # Existing Certifications & Projects
    curr_certs = [c.get("name") for c in (profile_obj.get("certifications") or []) if isinstance(c, dict) and c.get("name")]
    curr_projects = [p.get("title") for p in (profile_obj.get("projects") or []) if isinstance(p, dict) and p.get("title")]

    # Resume & Analysis Data
    resume_text = resumes[0].get("extracted_text", "") if resumes else "No uploaded resume."
    
    analysis_skills = []
    missing_analysis_skills = []
    if analyses:
        analysis_skills = analyses[0].get("technical_skills") or []
        missing_analysis_skills = analyses[0].get("missing_skills") or []

    # Job Match & Skill Gaps
    jm_summary = ""
    jm_missing_skills = []
    if job_matches:
        jm = job_matches[0]
        jm_missing_skills = jm.get("missing_skills") or []
        gaps_list = [f"{g.get('skill')}: {g.get('reason')}" for g in (jm.get("skill_gaps") or []) if isinstance(g, dict)]
        jm_summary = f"Job Match Role: {jm.get('job_title')}\nMatching: {', '.join(jm.get('matching_skills') or [])}\nMissing: {', '.join(jm_missing_skills)}\nSkill Gaps: {'; '.join(gaps_list)}"

    ats_summary = ""
    if ats_scores:
        ats = ats_scores[0]
        ats_summary = f"ATS Score: {ats.get('ats_score')}/100\nMissing Keywords: {', '.join(ats.get('missing_keywords') or [])}"

    interview_summary = ""
    if interviews:
        inv = interviews[0]
        interview_summary = f"Interview Prep Target: {inv.get('job_title')}\nIdentified Weaknesses: {', '.join(inv.get('potential_weaknesses') or [])}"

    prompt = f"""You are an expert career development and technical recruitment advisor for CareerPilot AI.

Create a realistic, personalized, and actionable career preparation roadmap for this specific user.
The objective is to help the user become genuinely prepared for the selected job role and company.

Do not provide generic career advice.
Analyze the user's current skills against the expected requirements of the target role and company.
Identify the most important missing skills and skill gaps.
Prioritize skills based on job relevance.
Recommend only technologies, subjects, certifications, and projects that meaningfully improve the user's readiness.

Do not invent certifications, companies, technologies, requirements or URLs.
If reliable certification information cannot be established, return an empty string for the certification URL rather than fabricating one.
The roadmap must be practical and achievable for the user's current level.

USER CAREER PROFILE:
- Target Company: {target_company}
- Target Job Role: {target_role}
- {edu_text}
- Current Verified Skills & Programming Languages: {', '.join(curr_prog_langs + curr_tech_skills) if (curr_prog_langs or curr_tech_skills) else 'None listed'}
- Current Tools & Platforms: {', '.join(curr_tools) if curr_tools else 'None listed'}
- Current Soft Skills: {', '.join(curr_soft_skills) if curr_soft_skills else 'None listed'}
- Existing Portfolio Projects: {', '.join(curr_projects) if curr_projects else 'None recorded'}
- Existing Certifications: {', '.join(curr_certs) if curr_certs else 'None recorded'}
- Identified Skill Gaps from Resume & Match Analysis: {', '.join(missing_analysis_skills + jm_missing_skills) if (missing_analysis_skills or jm_missing_skills) else 'Analyze gaps based on role requirements'}

--- RESUME TEXT CONTEXT ---
{resume_text[:2500]}

--- MATCH & ATS CONTEXT ---
{jm_summary if jm_summary else "No prior job match data recorded."}
{ats_summary if ats_summary else "No prior ATS analysis recorded."}
{interview_summary if interview_summary else "No prior interview session recorded."}

CRITICAL RULES FOR ROADMAP GENERATION:
1. Personalized Skill Gaps: Directly identify what this specific candidate lacks for {target_company} {target_role}. Provide a detailed 'skill_gaps' array with skill name, importance (High/Medium/Low), why needed, current level, and target level.
2. Logical Sequence: Follow a clear dependency progression:
   FOUNDATION -> CORE SKILLS -> ROLE-SPECIFIC TECHNOLOGIES -> ADVANCED SKILLS -> PROJECTS -> CERTIFICATION -> INTERVIEW READINESS.
3. Skill Prioritization: Categorize every skill into "High", "Medium", or "Low" priority:
   - High: Essential for {target_role} at {target_company} and candidate currently lacks it.
   - Medium: Highly recommended for proficiency.
   - Low: Good to have / future improvement.
   Provide a concrete 'reason' and 'what_to_learn' for each.
4. Clean Categorization: Provide distinct lists for programming languages, technologies, developer tools, and core academic subjects.
5. Certifications: Recommend ONLY 1 to 3 legitimate, highly relevant certifications for {target_company} + {target_role}. Provide provider, priority, rationale, and official certification website URL (or leave url empty if unavailable).
6. Portfolio Projects: Recommend 2 to 3 progressive projects (Beginner -> Intermediate -> Advanced Portfolio) specifically designed to demonstrate the missing skills. Include project title, difficulty, skills demonstrated, what to build, and why it helps.
7. Return ONLY a single raw valid JSON object matching this exact schema:

{{
  "career_goal": {{
    "company": "{target_company}",
    "role": "{target_role}"
  }},
  "current_readiness": {{
    "score": 65,
    "summary": "Concise summary of candidate's current capabilities, key skill gaps, and strategic focus for {target_company} {target_role}."
  }},
  "roadmap_duration": "10–12 weeks",
  "skill_gaps": [
    {{
      "skill": "Skill Name",
      "importance": "High",
      "reason": "Detailed explanation of why this skill is needed for {target_company} {target_role}.",
      "current_level": "Beginner / None",
      "target_level": "Intermediate / Production Ready"
    }}
  ],
  "phases": [
    {{
      "phase_number": 1,
      "title": "Phase Title (e.g. Core Foundations & System Mastery)",
      "duration": "2 weeks",
      "objective": "Clear milestone objective",
      "skills": [
        {{
          "name": "Skill Name",
          "priority": "High",
          "reason": "Why this skill is needed",
          "what_to_learn": "Key concepts and topics to master"
        }}
      ],
      "languages": ["Language 1"],
      "technologies": ["Tech 1"],
      "tools": ["Tool 1"],
      "core_subjects": ["Subject 1"],
      "certifications": [],
      "projects": [],
      "milestone": "Measurable milestone to complete this phase"
    }}
  ],
  "final_readiness": {{
    "technical_skills": ["Skill 1", "Skill 2"],
    "certifications_completed": ["Relevant Cert"],
    "projects_completed": ["Portfolio Project"],
    "interview_ready": false
  }}
}}

Constraints:
- Include between 3 and 5 well-structured sequential phases.
- Do NOT return markdown codeblocks or placeholder text. Return pure JSON.
"""

    if is_gemini_configured and genai_client:
        try:
            raw_text = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
            if raw_text and raw_text.strip():
                cleaned = clean_json_text(raw_text)
                parsed = json.loads(cleaned)
                return sanitize_and_validate_roadmap(parsed, target_company, target_role)
        except Exception as api_err:
            logger.warning(f"Gemini API call failed during career roadmap generation: {api_err}. Falling back to rule-based generator.")

    # Rule-based fallback generator
    logger.info(f"Career Roadmap Service: Using rule-based fallback generator for {target_role} at {target_company}.")
    fallback_data = generate_rule_based_roadmap(target_company, target_role, user_data)
    return sanitize_and_validate_roadmap(fallback_data, target_company, target_role)


def generate_rule_based_roadmap(company, role, user_data):
    """
    Generates a high-quality, customized career roadmap based on role and company requirements.
    """
    role_lower = role.lower()
    company_name = company or "Target Company"

    if any(k in role_lower for k in ["cyber", "security", "infosec", "soc", "penetration", "ethical"]):
        duration = "10–12 weeks"
        skill_gaps = [
            {"skill": "Network Security & Protocols", "importance": "High", "reason": f"Core foundation for {role} at {company_name}.", "current_level": "Beginner", "target_level": "Production Ready"},
            {"skill": "SIEM & Log Analysis (Splunk / ELK)", "importance": "High", "reason": f"Essential for real-time security monitoring at {company_name}.", "current_level": "Beginner", "target_level": "Intermediate"},
            {"skill": "Vulnerability Assessment & Penetration Testing", "importance": "High", "reason": "Identifying threats and CVE remediation.", "current_level": "None", "target_level": "Intermediate"},
            {"skill": "Cloud Security (AWS IAM / Azure Sentinel)", "importance": "Medium", "reason": "Securing cloud-native infrastructure.", "current_level": "Beginner", "target_level": "Competent"},
            {"skill": "Incident Response & Forensics", "importance": "Medium", "reason": "Handling enterprise security breaches and threat mitigation.", "current_level": "None", "target_level": "Intermediate"}
        ]
        phases = [
            {
                "phase_number": 1,
                "title": "Phase 1: Networking, OS Internals & Security Foundations",
                "duration": "3 weeks",
                "objective": f"Master foundational security concepts, TCP/IP networking, Linux CLI, and defensive architecture for {company_name}.",
                "skills": [
                    {"name": "TCP/IP & OSI Model", "priority": "High", "reason": "Essential for packet inspection and network security.", "what_to_learn": "Packet flow, DNS, DHCP, TLS/SSL, Wireshark analysis."},
                    {"name": "Linux Security & Command Line", "priority": "High", "reason": "Server administration and incident handling.", "what_to_learn": "Permissions, iptables, SSH hardening, bash scripting."},
                    {"name": "Cryptography Basics", "priority": "Medium", "reason": "Data encryption and authentication standards.", "what_to_learn": "Symmetric vs Asymmetric, Hashing (SHA-256), PKI."}
                ],
                "languages": ["Python", "Bash"],
                "technologies": ["Linux", "Wireshark", "OpenVPN"],
                "tools": ["Nmap", "Wireshark", "Tcpdump"],
                "core_subjects": ["Computer Networks", "Operating Systems", "Information Security Principles"],
                "certifications": [
                    {"name": "CompTIA Security+", "provider": "CompTIA", "priority": "High", "url": "https://www.comptia.org/certifications/security", "status": "recommended"}
                ],
                "projects": [
                    {
                        "title": "Network Traffic & Threat Packet Analyzer",
                        "difficulty": "Beginner",
                        "skills": ["Python", "Scapy", "Wireshark"],
                        "what_to_build": "Build a Python CLI tool to capture live packets, parse headers, and detect port-scanning attempts in real-time.",
                        "expected_outcome": "Working packet capture script committed to GitHub with detection logs.",
                        "status": "not_started"
                    }
                ],
                "milestone": "Successfully analyze network packet dumps and implement basic Linux firewall rules."
            },
            {
                "phase_number": 2,
                "title": "Phase 2: Threat Detection, SIEM & Security Operations",
                "duration": "3 weeks",
                "objective": "Build practical skills in security monitoring, log analysis, threat intelligence, and vulnerability scanning.",
                "skills": [
                    {"name": "SIEM Tools & Log Ingestion", "priority": "High", "reason": f"Directly expected in SOC and {role} roles at {company_name}.", "what_to_learn": "Splunk SPL queries, ELK stack setup, correlation rules."},
                    {"name": "Vulnerability Scanning", "priority": "High", "reason": "Discovering unpatched vulnerabilities and misconfigurations.", "what_to_learn": "Nessus, OpenVAS, CVSS score interpretation."},
                    {"name": "MITRE ATT&CK Framework", "priority": "Medium", "reason": "Standard methodology for threat classification.", "what_to_learn": "Adversary tactics, techniques, and mapping alert detections."}
                ],
                "languages": ["Python", "SQL"],
                "technologies": ["Splunk", "ELK Stack", "Snort / Suricata"],
                "tools": ["Nessus", "Burp Suite", "Splunk Enterprise"],
                "core_subjects": ["Network Security", "Threat Intelligence", "Security Operations"],
                "certifications": [
                    {"name": "Certified Ethical Hacker (CEH) or eJPT", "provider": "EC-Council / INE", "priority": "High", "url": "https://www.eccouncil.org/programs/certified-ethical-hacker-ceh/", "status": "recommended"}
                ],
                "projects": [
                    {
                        "title": "SOC Automation & Incident Detection Lab",
                        "difficulty": "Intermediate",
                        "skills": ["Splunk", "Python", "Sysmon", "SIEM"],
                        "what_to_build": "Configure a local SIEM lab forwarding Windows Sysmon logs to Splunk, triggering automated alerts on brute-force login attempts.",
                        "expected_outcome": "Documented home lab setup with custom SPL alert rules and incident playbook.",
                        "status": "not_started"
                    }
                ],
                "milestone": "Deploy a working SIEM lab and configure custom detection alerts for common attack vectors."
            },
            {
                "phase_number": 3,
                "title": "Phase 3: Web Security, Penetration Testing & Cloud Hardening",
                "duration": "3 weeks",
                "objective": "Learn application security fundamentals, OWASP Top 10 vulnerabilities, and cloud security compliance.",
                "skills": [
                    {"name": "OWASP Top 10 Exploitation & Defense", "priority": "High", "reason": "Securing web services and API endpoints.", "what_to_learn": "SQL Injection, XSS, CSRF, SSRF, Broken Access Control."},
                    {"name": "Cloud Security & IAM", "priority": "High", "reason": f"Enterprise cloud governance at {company_name}.", "what_to_learn": "AWS IAM policies, Security Groups, Azure Sentinel, cloud compliance."},
                    {"name": "API Security & Token Verification", "priority": "Medium", "reason": "Protecting modern microservice APIs.", "what_to_learn": "JWT validation, OAuth2 flows, rate limiting."}
                ],
                "languages": ["Python", "JavaScript / Go"],
                "technologies": ["AWS / Azure", "Docker", "Burp Suite"],
                "tools": ["Burp Suite Community", "Postman", "OWASP ZAP", "Trivy"],
                "core_subjects": ["Web Application Security", "Cloud Computing Security"],
                "certifications": [
                    {"name": "AWS Certified Security - Specialty", "provider": "Amazon Web Services", "priority": "Medium", "url": "https://aws.amazon.com/certification/certified-security-specialty/", "status": "recommended"}
                ],
                "projects": [
                    {
                        "title": "Automated Web Vulnerability & API Scanner",
                        "difficulty": "Advanced",
                        "skills": ["Python", "Requests", "OWASP ZAP API", "Docker"],
                        "what_to_build": "Develop a containerized API scanner that tests web applications for SQLi, XSS, and misconfigured HTTP headers, generating PDF audit reports.",
                        "expected_outcome": "Complete GitHub repository with automated CI/CD security check and report generation.",
                        "status": "not_started"
                    }
                ],
                "milestone": "Conduct full vulnerability assessment on a vulnerable web application and draft remediation report."
            },
            {
                "phase_number": 4,
                "title": f"Phase 4: {company_name} Interview Prep & Mock Assessments",
                "duration": "2 weeks",
                "objective": f"Sharpen technical interview skills, scenario-based defense questions, and {company_name} recruitment patterns.",
                "skills": [
                    {"name": "Incident Response Playbooks", "priority": "High", "reason": f"Commonly asked in {company_name} security technical interviews.", "what_to_learn": "Triage, containment, eradication, lessons learned methodology."},
                    {"name": "System Architecture Defense", "priority": "High", "reason": "Designing secure multi-tier enterprise systems.", "what_to_learn": "Zero Trust architecture, DMZ layout, WAF configuration."},
                    {"name": "Behavioral & Technical Mock Interviews", "priority": "High", "reason": "Confidence in live technical evaluations.", "what_to_learn": "STAR method responses for security projects and troubleshooting."}
                ],
                "languages": ["Python"],
                "technologies": ["Enterprise Security Architecture", "Zero Trust"],
                "tools": ["CareerPilot Interview Prep", "Wireshark", "Linux Terminal"],
                "core_subjects": ["Incident Response", "Security Architecture & Compliance"],
                "certifications": [],
                "projects": [],
                "milestone": f"Complete 5+ company mock interview simulations for {company_name} and finalize technical portfolio."
            }
        ]
        readiness_score = 65
        profile_summary = f"Customized technical roadmap designed for {company_name} {role}, focusing on networking foundations, SIEM log monitoring, OWASP web application security, and incident response."
    else:
        # Software Engineer / General Developer Roadmap
        duration = "10–12 weeks"
        skill_gaps = [
            {"skill": "Data Structures & Algorithms", "importance": "High", "reason": f"Essential for technical assessments at {company_name}.", "current_level": "Intermediate", "target_level": "Advanced"},
            {"skill": "System Design & Architecture", "importance": "High", "reason": f"Required for {role} engineering standards.", "current_level": "Beginner", "target_level": "Intermediate"},
            {"skill": "Modern Frameworks & API Design", "importance": "High", "reason": "Building production-grade scalable services.", "current_level": "Intermediate", "target_level": "Production Ready"},
            {"skill": "Cloud Deployment & CI/CD", "importance": "Medium", "reason": "Deploying containerized microservices.", "current_level": "Beginner", "target_level": "Intermediate"}
        ]
        phases = [
            {
                "phase_number": 1,
                "title": "Phase 1: Advanced Algorithms, Data Structures & Coding Patterns",
                "duration": "3 weeks",
                "objective": f"Master core algorithms, complexity analysis, and problem-solving patterns required for {company_name}.",
                "skills": [
                    {"name": "Arrays, HashMaps & Two Pointers", "priority": "High", "reason": "Core foundation of technical coding interviews.", "what_to_learn": "Sliding window, prefix sums, binary search."},
                    {"name": "Trees, Graphs & Dynamic Programming", "priority": "High", "reason": "Frequent coding assessment questions.", "what_to_learn": "BFS/DFS, Dijkstra, Top-down and bottom-up DP."}
                ],
                "languages": ["Java / Python / C++"],
                "technologies": ["Git", "Data Structures"],
                "tools": ["VS Code", "LeetCode / HackerRank"],
                "core_subjects": ["Data Structures & Algorithms", "Discrete Mathematics"],
                "certifications": [],
                "projects": [],
                "milestone": "Solve 75+ targeted algorithmic problems and achieve proficiency in Big-O optimization."
            },
            {
                "phase_number": 2,
                "title": "Phase 2: Backend Architecture, Databases & API Engineering",
                "duration": "3 weeks",
                "objective": "Build robust REST/GraphQL APIs, database models, caching mechanisms, and authentication.",
                "skills": [
                    {"name": "RESTful API Design & Best Practices", "priority": "High", "reason": "Industry standard for service communication.", "what_to_learn": "Status codes, pagination, rate limiting, JWT auth."},
                    {"name": "Database Schema Design & Query Optimization", "priority": "High", "reason": "Handling enterprise data efficiently.", "what_to_learn": "PostgreSQL, Indexing, Transactions, NoSQL."}
                ],
                "languages": ["Python / JavaScript / Java"],
                "technologies": ["Node.js / FastAPI / Spring Boot", "PostgreSQL", "Redis"],
                "tools": ["Postman", "Docker", "DBeaver"],
                "core_subjects": ["Database Management Systems", "Object-Oriented Design"],
                "certifications": [],
                "projects": [
                    {
                        "title": "Scalable RESTful Backend with Caching & Auth",
                        "difficulty": "Intermediate",
                        "skills": ["REST API", "Database", "Redis", "Docker"],
                        "what_to_build": "Implement a full authentication and resource management API featuring Redis caching and JWT security.",
                        "expected_outcome": "Containerized backend repository with automated tests.",
                        "status": "not_started"
                    }
                ],
                "milestone": "Deploy a containerized API backed by a relational database and Redis caching."
            },
            {
                "phase_number": 3,
                "title": "Phase 3: System Design, Cloud Deployment & CI/CD",
                "duration": "3 weeks",
                "objective": "Master high-level system design concepts, microservices, messaging queues, and automated deployments.",
                "skills": [
                    {"name": "System Design Fundamentals", "priority": "High", "reason": f"Required for {role} interviews at {company_name}.", "what_to_learn": "Load balancing, horizontal scaling, CAP theorem, message queues."},
                    {"name": "Docker & Cloud Deployment", "priority": "Medium", "reason": "Cloud-native application lifecycle.", "what_to_learn": "Dockerfile creation, AWS ECS/S3, GitHub Actions CI/CD."}
                ],
                "languages": ["Python / JavaScript"],
                "technologies": ["Docker", "AWS / GCP", "GitHub Actions"],
                "tools": ["Docker Compose", "AWS Console", "Git"],
                "core_subjects": ["Distributed Systems", "Cloud Computing"],
                "certifications": [
                    {"name": "AWS Certified Cloud Practitioner or Developer", "provider": "AWS", "priority": "Medium", "url": "https://aws.amazon.com/certification/certified-cloud-practitioner/", "status": "recommended"}
                ],
                "projects": [
                    {
                        "title": "Full-Stack Cloud-Deployed Application",
                        "difficulty": "Advanced",
                        "skills": ["Full Stack", "Docker", "CI/CD", "Cloud"],
                        "what_to_build": "End-to-end full-stack web application featuring automated GitHub Actions CI/CD pipeline and cloud hosting.",
                        "expected_outcome": "Live deployed web application with public URL and documented architecture.",
                        "status": "not_started"
                    }
                ],
                "milestone": "Successfully complete high-level system design architectures and deploy an end-to-end project."
            },
            {
                "phase_number": 4,
                "title": f"Phase 4: {company_name} Interview Readiness & Behavioral Mastery",
                "duration": "2 weeks",
                "objective": f"Final interview preparation targeting {company_name}'s specific hiring rounds and technical bars.",
                "skills": [
                    {"name": "Live Technical Problem Solving", "priority": "High", "reason": f"Passing {company_name} live coding rounds.", "what_to_learn": "Thinking aloud, test cases validation, clean code standards."},
                    {"name": "Behavioral Leadership Principles", "priority": "High", "reason": "Managerial and HR interview rounds.", "what_to_learn": "STAR technique for past projects, conflict resolution, ownership."}
                ],
                "languages": ["Target Language"],
                "technologies": ["Company Tech Stack"],
                "tools": ["CareerPilot AI Interview Trainer"],
                "core_subjects": ["Software Engineering Principles", "Communication"],
                "certifications": [],
                "projects": [],
                "milestone": f"Complete mock interview sessions for {company_name} and finalize your polished resume."
            }
        ]
        readiness_score = 65
        profile_summary = f"Comprehensive career roadmap for {company_name} {role}, balancing algorithmic problem-solving, backend architecture, system design, and interview readiness."

    return {
        "career_goal": {"company": company_name, "role": role},
        "current_readiness": {"score": readiness_score, "summary": profile_summary},
        "readiness_score": readiness_score,
        "readiness_label": get_readiness_label(readiness_score),
        "roadmap_duration": duration,
        "skill_gaps": skill_gaps,
        "phases": phases,
        "recommended_projects": [pr for ph in phases for pr in ph.get("projects", [])],
        "final_readiness": {
            "technical_skills": [s.get("name") for ph in phases for s in ph.get("skills", [])][:6],
            "certifications_completed": [c.get("name") for ph in phases for c in ph.get("certifications", [])],
            "projects_completed": [pr.get("title") for ph in phases for pr in ph.get("projects", [])],
            "interview_ready": False
        }
    }


def sanitize_and_validate_roadmap(parsed, default_company="Target Company", default_role="Software Engineer"):
    """
    Validates and standardizes the AI roadmap schema, adding defaults where needed.
    """
    from backend.services.resume_intelligence import deduplicate_list

    if not isinstance(parsed, dict):
        parsed = {}

    # 1. Career Goal
    cg = parsed.get("career_goal")
    if not isinstance(cg, dict):
        cg = {}
    company = str(cg.get("company") or default_company).strip()
    role = str(cg.get("role") or default_role).strip()
    parsed["career_goal"] = {"company": company, "role": role}

    # 2. Current Readiness
    cr = parsed.get("current_readiness")
    if not isinstance(cr, dict):
        cr = {}
    try:
        score = max(0, min(100, int(cr.get("score", parsed.get("readiness_score", 60)))))
    except (ValueError, TypeError):
        score = 60
    summary = str(cr.get("summary") or parsed.get("current_profile_summary") or f"Roadmap for {role} at {company}.").strip()
    parsed["current_readiness"] = {
        "score": score,
        "summary": summary
    }

    # Backward compatibility root scores
    parsed["readiness_score"] = score
    parsed["readiness_label"] = get_readiness_label(score)
    parsed["roadmap_duration"] = str(parsed.get("roadmap_duration") or parsed.get("estimated_timeline") or "8–12 weeks").strip()

    # 3. Dynamic Skill Gaps Validation
    raw_gaps = parsed.get("skill_gaps") or []
    sanitized_gaps = []
    if isinstance(raw_gaps, list):
        for g in raw_gaps:
            if isinstance(g, dict) and g.get("skill"):
                imp = str(g.get("importance") or "High").capitalize()
                if imp not in ["High", "Medium", "Low"]:
                    imp = "High"
                sanitized_gaps.append({
                    "skill": str(g.get("skill")).strip(),
                    "importance": imp,
                    "reason": str(g.get("reason") or f"Required for {company} {role} competency.").strip(),
                    "current_level": str(g.get("current_level") or "Beginner").strip(),
                    "target_level": str(g.get("target_level") or "Production Ready").strip()
                })
            elif isinstance(g, str) and g.strip():
                sanitized_gaps.append({
                    "skill": g.strip(),
                    "importance": "High",
                    "reason": f"Required competency for {role}.",
                    "current_level": "Needs Improvement",
                    "target_level": "Intermediate / Job Ready"
                })
    parsed["skill_gaps"] = sanitized_gaps

    # 4. Phases validation
    raw_phases = parsed.get("phases") or parsed.get("roadmap") or []
    if not isinstance(raw_phases, list):
        raw_phases = []

    sanitized_phases = []
    for idx, p in enumerate(raw_phases):
        if not isinstance(p, dict):
            continue

        p_num = p.get("phase_number") or p.get("phase") or (idx + 1)
        p_title = str(p.get("title") or f"Phase {p_num}").strip()
        p_duration = str(p.get("duration") or p.get("estimated_duration") or "2 weeks").strip()
        p_obj = str(p.get("objective") or p.get("description") or "").strip()
        p_milestone = str(p.get("milestone") or (p.get("success_criteria")[0] if p.get("success_criteria") else "")).strip()

        # Skills with priorities
        raw_skills = p.get("skills") or []
        sanitized_skills = []
        if isinstance(raw_skills, list):
            for s in raw_skills:
                if isinstance(s, dict):
                    priority = str(s.get("priority") or "High").capitalize()
                    if priority not in ["High", "Medium", "Low"]:
                        priority = "High"
                    sanitized_skills.append({
                        "name": str(s.get("name") or "Skill").strip(),
                        "priority": priority,
                        "reason": str(s.get("reason") or "").strip(),
                        "what_to_learn": str(s.get("what_to_learn") or "").strip(),
                        "status": str(s.get("status") or "not_started").strip()
                    })
                elif isinstance(s, str) and s.strip():
                    sanitized_skills.append({
                        "name": s.strip(),
                        "priority": "High",
                        "reason": "Core competency for this phase.",
                        "what_to_learn": f"Master {s.strip()} fundamentals and hands-on usage.",
                        "status": "not_started"
                    })

        # If no skills in skills list, check skills_to_develop
        if not sanitized_skills and p.get("skills_to_develop"):
            for s_str in p.get("skills_to_develop", []):
                if isinstance(s_str, str) and s_str.strip():
                    sanitized_skills.append({
                        "name": s_str.strip(),
                        "priority": "High",
                        "reason": "Required phase skill.",
                        "what_to_learn": f"Learn practical {s_str.strip()}.",
                        "status": "not_started"
                    })

        # Certifications inside phase
        raw_certs = p.get("certifications") or []
        sanitized_certs = []
        if isinstance(raw_certs, list):
            for c in raw_certs:
                if isinstance(c, dict):
                    sanitized_certs.append({
                        "name": str(c.get("name") or "Certification").strip(),
                        "provider": str(c.get("provider") or "").strip(),
                        "priority": str(c.get("priority") or "High").strip(),
                        "reason": str(c.get("reason") or "").strip(),
                        "url": str(c.get("url") or c.get("official_url") or "").strip(),
                        "status": str(c.get("status") or "not_started").strip()
                    })
                elif isinstance(c, str) and c.strip():
                    sanitized_certs.append({
                        "name": c.strip(),
                        "provider": company,
                        "priority": "High",
                        "reason": "Directly relevant certification.",
                        "url": "",
                        "status": "not_started"
                    })

        # Projects inside phase
        raw_projects = p.get("projects") or []
        sanitized_projects = []
        if isinstance(raw_projects, list):
            for pr in raw_projects:
                if isinstance(pr, dict):
                    sanitized_projects.append({
                        "title": str(pr.get("title") or pr.get("name") or "Portfolio Project").strip(),
                        "difficulty": str(pr.get("difficulty") or "Intermediate").strip(),
                        "skills": deduplicate_list(pr.get("skills") or []),
                        "what_to_build": str(pr.get("what_to_build") or pr.get("description") or "").strip(),
                        "expected_outcome": str(pr.get("expected_outcome") or "").strip(),
                        "status": str(pr.get("status") or "not_started").strip()
                    })
                elif isinstance(pr, str) and pr.strip():
                    sanitized_projects.append({
                        "title": pr.strip(),
                        "difficulty": "Intermediate",
                        "skills": [],
                        "what_to_build": f"Implement a working solution for {pr.strip()}.",
                        "expected_outcome": "Working repository deployed to portfolio.",
                        "status": "not_started"
                    })

        sanitized_phases.append({
            "phase_number": p_num,
            "title": p_title,
            "duration": p_duration,
            "objective": p_obj,
            "skills": sanitized_skills,
            "languages": deduplicate_list(p.get("languages") or []),
            "technologies": deduplicate_list(p.get("technologies") or []),
            "tools": deduplicate_list(p.get("tools") or []),
            "core_subjects": deduplicate_list(p.get("core_subjects") or []),
            "certifications": sanitized_certs,
            "projects": sanitized_projects,
            "milestone": p_milestone,
            "status": str(p.get("status") or "not_started").strip()
        })

    parsed["phases"] = sanitized_phases
    # Maintain backward compatibility 'roadmap' key
    parsed["roadmap"] = sanitized_phases

    # 4. Final Readiness
    fr = parsed.get("final_readiness")
    if not isinstance(fr, dict):
        fr = {}
    parsed["final_readiness"] = {
        "technical_skills": deduplicate_list(fr.get("technical_skills") or []),
        "certifications_completed": deduplicate_list(fr.get("certifications_completed") or []),
        "projects_completed": deduplicate_list(fr.get("projects_completed") or []),
        "interview_ready": bool(fr.get("interview_ready", False))
    }

    # Consolidated project list & certifications
    all_projects = []
    for ph in sanitized_phases:
        for pr in ph.get("projects", []):
            all_projects.append(pr)
    parsed["recommended_projects"] = all_projects if all_projects else deduplicate_list(parsed.get("recommended_projects") or [])

    parsed["progress"] = parsed.get("progress", 0)

    return parsed

