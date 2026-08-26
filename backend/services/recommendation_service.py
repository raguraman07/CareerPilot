"""
CareerPilot AI — Certification & Project Recommendation Engine Service (Phase 7)

Grounded in:
Career Goal + Target Company + Target Role + Candidate Profile + Resume +
Phase 3 Assessment + Phase 4 Learning Plan + Phase 5 Verified Skills + Phase 6 Interview Performance.

Delivers:
- Role-Grounded Certifications (Must Complete, Recommended, Advanced) with strictly official verified URLs
- Portfolio-Worthy Projects (Beginner, Intermediate, Advanced) with problem statement, architecture, features, and resume impact
"""

import os
import json
import logging
import uuid as uuid_lib
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure environment variables are loaded
_backend_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)
else:
    load_dotenv()

from services.resume_intelligence import (
    call_gemini_with_retry,
    clean_json_text,
    genai_client,
    is_gemini_configured
)

# Whitelist of verified, official certification provider domains
OFFICIAL_DOMAINS = (
    "learn.microsoft.com",
    "aws.amazon.com",
    "cloud.google.com",
    "skillsbuild.ibm.com",
    "netacad.com",
    "training.linuxfoundation.org",
    "oracle.com",
    "coursera.org",
    "edx.org",
    "hashicorp.com",
    "cncf.io",
    "redhat.com"
)

def sanitize_official_url(url, provider="Microsoft"):
    """Ensures certification URLs point to verified official provider domains."""
    if not url or not isinstance(url, str):
        return "https://learn.microsoft.com/"
    
    url_lower = url.lower().strip()
    if any(domain in url_lower for domain in OFFICIAL_DOMAINS):
        return url.strip()
    
    # Safe default fallbacks based on provider
    p_lower = provider.lower()
    if "aws" in p_lower or "amazon" in p_lower:
        return "https://aws.amazon.com/certification/"
    elif "google" in p_lower or "gcp" in p_lower:
        return "https://cloud.google.com/learn/certification"
    elif "linux" in p_lower:
        return "https://training.linuxfoundation.org/certification/"
    elif "ibm" in p_lower:
        return "https://skillsbuild.ibm.com/"
    elif "cisco" in p_lower:
        return "https://www.netacad.com/"
    elif "oracle" in p_lower:
        return "https://education.oracle.com/"
    return "https://learn.microsoft.com/en-us/credentials/"


def validate_recommendations_json(data):
    """Validates the structure of generated recommendations."""
    if not isinstance(data, dict):
        return False
    
    certs = data.get("certifications")
    projs = data.get("projects")
    
    if not isinstance(certs, dict) or not isinstance(projs, dict):
        return False
    
    # Check certification tiers
    for tier in ["must_complete", "recommended", "advanced"]:
        if tier not in certs or not isinstance(certs[tier], list):
            return False
            
    # Check project tiers
    for tier in ["beginner", "intermediate", "advanced"]:
        if tier not in projs or not isinstance(projs[tier], list):
            return False
            
    return True


def generate_fallback_recommendations(goal, profile, resume, assessment, learning_plan):
    """
    Robust rule-based generator for role-grounded certifications and portfolio projects.
    """
    company = goal.get("company_name", "Microsoft")
    role = goal.get("job_role", "Cloud Engineer")
    exp_level = goal.get("experience_level", "Fresher")

    # Determine primary focus based on role
    role_lower = role.lower()
    is_cloud = any(k in role_lower for k in ["cloud", "devops", "sre", "infrastructure", "platform"])
    is_data = any(k in role_lower for k in ["data", "analytics", "bi", "machine learning", "ai", "scientist"])

    if is_cloud:
        must_certs = [
            {
                "id": "cert-az900",
                "name": "Microsoft Certified: Azure Fundamentals (AZ-900)",
                "provider": "Microsoft",
                "difficulty": "Beginner",
                "duration": "15 Hours",
                "why_useful": f"Foundational validation of cloud architecture, compute, networking, and governance essential for {role} roles at {company}.",
                "skills_improved": ["Cloud Architecture", "Azure Core Services", "Security & Governance"],
                "target_alignment": f"{company} {role}",
                "official_url": "https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/",
                "category": "must_complete"
            },
            {
                "id": "cert-lfs",
                "name": "Linux Foundation Certified System Administrator (LFCS)",
                "provider": "Linux Foundation",
                "difficulty": "Intermediate",
                "duration": "30 Hours",
                "why_useful": "Demonstrates hands-on Linux system administration, storage, and networking proficiency required in production cloud environments.",
                "skills_improved": ["Linux Admin", "Shell Scripting", "Storage & Permissions"],
                "target_alignment": f"Infrastructure & Platform Engineering at {company}",
                "official_url": "https://training.linuxfoundation.org/certification/linux-foundation-certified-sysadmin-lfcs/",
                "category": "must_complete"
            }
        ]
        rec_certs = [
            {
                "id": "cert-az104",
                "name": "Microsoft Certified: Azure Administrator Associate (AZ-104)",
                "provider": "Microsoft",
                "difficulty": "Intermediate",
                "duration": "40 Hours",
                "why_useful": "Validates deep implementation of identity, governance, virtual networking, and storage in Azure.",
                "skills_improved": ["Virtual Networking", "Azure Active Directory", "VM Scalability"],
                "target_alignment": f"{role} Core Competency",
                "official_url": "https://learn.microsoft.com/en-us/credentials/certifications/azure-administrator/",
                "category": "recommended"
            },
            {
                "id": "cert-dca",
                "name": "Docker Certified Associate (DCA)",
                "provider": "Docker / Mirantis",
                "difficulty": "Intermediate",
                "duration": "25 Hours",
                "why_useful": "Proves container orchestration, image creation, multi-stage builds, and Docker networking capabilities.",
                "skills_improved": ["Containerization", "Docker Compose", "Multi-stage Builds"],
                "target_alignment": "Containerized Deployments",
                "official_url": "https://training.linuxfoundation.org/certification/",
                "category": "recommended"
            }
        ]
        adv_certs = [
            {
                "id": "cert-cka",
                "name": "Certified Kubernetes Administrator (CKA)",
                "provider": "Cloud Native Computing Foundation (CNCF)",
                "difficulty": "Advanced",
                "duration": "60 Hours",
                "why_useful": "Industry standard credential proving mastery of Kubernetes cluster architecture, networking, pod security, and troubleshooting.",
                "skills_improved": ["Kubernetes Clusters", "Service Mesh", "Ingress Controllers", "Pod Security"],
                "target_alignment": f"Senior {role} & SRE roles",
                "official_url": "https://www.cncf.io/certification/cka/",
                "category": "advanced"
            }
        ]
        projects_beginner = [
            {
                "id": "proj-b1",
                "title": "Containerized Microservices Health Monitor",
                "difficulty": "Beginner",
                "estimated_duration": "1-2 Weeks",
                "technologies": ["Python", "Flask", "Docker", "REST APIs"],
                "skills_demonstrated": ["Docker Containerization", "Health Probes", "REST API Development"],
                "real_world_problem": "Microservices in production require automated health checks and latency monitoring to prevent silent downtime.",
                "features": ["Automated HTTP endpoint latency probing", "Dockerized container deployment", "JSON health metrics endpoint", "Environment-based configuration"],
                "folder_structure": "health-monitor/\n├── app/\n│   ├── __init__.py\n│   ├── monitor.py\n│   └── routes.py\n├── Dockerfile\n├── docker-compose.yml\n└── requirements.txt",
                "deployment_suggestion": "Deploy container on Render or Azure Container Apps",
                "resume_impact": "Engineered a containerized microservice monitoring suite in Python/Flask that conducts automated health probes and exports real-time service metrics.",
                "why_build_this": "Directly proves foundational Docker containerization and clean REST API structure."
            },
            {
                "id": "proj-b2",
                "title": "Automated Cloud Resource Backup Script",
                "difficulty": "Beginner",
                "estimated_duration": "1 Week",
                "technologies": ["Bash", "Linux", "Azure CLI", "Cron"],
                "skills_demonstrated": ["Shell Scripting", "Linux Crontab", "CLI Automation"],
                "real_world_problem": "Manual backup operations risk human error and compliance failure.",
                "features": ["Automated daily snapshot creation", "Log retention & rotation", "Error alerting via webhook"],
                "folder_structure": "cloud-backup/\n├── scripts/\n│   ├── backup.sh\n│   └── alert.sh\n└── crontab.sample",
                "deployment_suggestion": "Run as a scheduled cron service on Linux VM",
                "resume_impact": "Automated database and storage snapshot backups using Bash scripts and Linux cron with error notification webhooks.",
                "why_build_this": "Demonstrates essential Linux administration and shell automation skills required for cloud roles."
            }
        ]
        projects_intermediate = [
            {
                "id": "proj-i1",
                "title": "Multi-Environment CI/CD Deployment Pipeline",
                "difficulty": "Intermediate",
                "estimated_duration": "2-3 Weeks",
                "technologies": ["GitHub Actions", "Docker", "Azure CLI", "Python"],
                "skills_demonstrated": ["CI/CD Automation", "Docker Registry", "Multi-Environment Staging"],
                "real_world_problem": "Manual deployments cause downtime and environment configuration drift.",
                "features": ["Automated unit test execution on pull request", "Docker image build & push to registry", "Zero-downtime deployment staging", "Secrets management"],
                "folder_structure": "cicd-pipeline/\n├── .github/\n│   └── workflows/\n│       ├── test.yml\n│       └── deploy.yml\n├── src/\n├── Dockerfile\n└── README.md",
                "deployment_suggestion": "GitHub Actions deploying to Azure App Service",
                "resume_impact": "Constructed an automated CI/CD pipeline using GitHub Actions and Docker that reduced deployment turnaround from hours to minutes.",
                "why_build_this": "Solves a critical skill gap in CI/CD and deployment workflows highly emphasized at enterprise tech companies."
            },
            {
                "id": "proj-i2",
                "title": "High-Availability Web Application with Redis Caching",
                "difficulty": "Intermediate",
                "estimated_duration": "3 Weeks",
                "technologies": ["Flask", "PostgreSQL", "Redis", "Docker Compose"],
                "skills_demonstrated": ["Database Connection Pooling", "In-Memory Caching", "Container Networking"],
                "real_world_problem": "Database bottlenecks degrade application performance under concurrent traffic spikes.",
                "features": ["Redis cache-aside pattern", "PostgreSQL connection pooling", "Docker Compose multi-container networking", "Rate limiting"],
                "folder_structure": "ha-web-app/\n├── app/\n├── docker-compose.yml\n├── nginx.conf\n└── requirements.txt",
                "deployment_suggestion": "Multi-container deployment on Cloud VM with Nginx reverse proxy",
                "resume_impact": "Developed a high-availability backend with Redis caching and PostgreSQL pooling that handles high-concurrency requests with low latency.",
                "why_build_this": "Proves your ability to design robust backend architectures that scale gracefully."
            },
            {
                "id": "proj-i3",
                "title": "Infrastructure-as-Code Cloud Provisioner",
                "difficulty": "Intermediate",
                "estimated_duration": "2-3 Weeks",
                "technologies": ["Terraform", "Azure Resource Manager", "Bash"],
                "skills_demonstrated": ["Infrastructure as Code", "Cloud Networking", "Security Groups"],
                "real_world_problem": "Cloud infrastructure must be reproducible, version-controlled, and auditable.",
                "features": ["Modular Virtual Network and Subnet creation", "Network Security Group rules enforcement", "Automated VM provisioning", "State management"],
                "folder_structure": "terraform-infra/\n├── modules/\n│   ├── network/\n│   └── compute/\n├── main.tf\n├── variables.tf\n└── outputs.tf",
                "deployment_suggestion": "Terraform Cloud or local Azure CLI execution",
                "resume_impact": "Implemented Infrastructure-as-Code modules using Terraform to automatically provision secure Virtual Networks and compute instances.",
                "why_build_this": "IaC is one of the highest-demand skills for modern Cloud and DevOps engineers."
            }
        ]
        projects_advanced = [
            {
                "id": "proj-a1",
                "title": "Resilient Kubernetes Microservices Cluster with Ingress & Observability",
                "difficulty": "Advanced",
                "estimated_duration": "4-5 Weeks",
                "technologies": ["Kubernetes", "Docker", "Prometheus", "Grafana", "Helm"],
                "skills_demonstrated": ["Kubernetes Deployment & Services", "Ingress Routing", "Cluster Monitoring & Metrics", "Helm Charts"],
                "real_world_problem": "Enterprise applications require self-healing container orchestration, zero-downtime rolling updates, and full observability.",
                "features": ["Horizontal Pod Autoscaling (HPA)", "Nginx Ingress Controller with SSL termination", "Prometheus metrics scrapers & Grafana dashboards", "Helm package distribution"],
                "folder_structure": "k8s-platform/\n├── helm-charts/\n├── k8s-manifests/\n│   ├── deployment.yaml\n│   ├── ingress.yaml\n│   └── hpa.yaml\n├── services/\n└── monitoring/",
                "deployment_suggestion": "Azure Kubernetes Service (AKS) or Minikube local cluster",
                "resume_impact": "Architected a Kubernetes microservices cluster with Horizontal Pod Autoscaling, Helm charts, and Prometheus/Grafana real-time observability.",
                "why_build_this": "Distinguishes you as an advanced candidate capable of production Kubernetes cluster management."
            },
            {
                "id": "proj-a2",
                "title": "Distributed Event-Driven Task Queue Platform",
                "difficulty": "Advanced",
                "estimated_duration": "4 Weeks",
                "technologies": ["Python", "Celery", "RabbitMQ", "Redis", "Docker"],
                "skills_demonstrated": ["Asynchronous Architecture", "Message Brokers", "Dead Letter Queues", "Fault Isolation"],
                "real_world_problem": "Heavy compute tasks (e.g. AI processing, PDF parsing) must execute asynchronously without blocking user web requests.",
                "features": ["Distributed task dispatching with RabbitMQ broker", "Dead letter queue retry mechanism", "Worker concurrency scaling", "Task status monitoring dashboard"],
                "folder_structure": "task-queue-platform/\n├── workers/\n├── web_api/\n├── docker-compose.yml\n└── config.py",
                "deployment_suggestion": "Docker swarm or cloud VM cluster with containerized workers",
                "resume_impact": "Built a scalable distributed task queue in Python and Celery utilizing RabbitMQ to process background workloads asynchronously with automatic failure retry.",
                "why_build_this": "Directly models the asynchronous event architecture utilized in enterprise software systems."
            }
        ]
    else:
        # Default / Software Engineering Track
        must_certs = [
            {
                "id": "cert-se1",
                "name": "Meta Back-End Developer Professional Certificate",
                "provider": "Meta / Coursera",
                "difficulty": "Beginner",
                "duration": "40 Hours",
                "why_useful": f"Validates REST API design, database modeling, and version control for {role} at {company}.",
                "skills_improved": ["REST APIs", "Python/Django", "Database Systems", "Git"],
                "target_alignment": f"{company} {role}",
                "official_url": "https://www.coursera.org/professional-certificates/meta-back-end-developer",
                "category": "must_complete"
            }
        ]
        rec_certs = [
            {
                "id": "cert-se2",
                "name": "AWS Certified Cloud Practitioner",
                "provider": "AWS",
                "difficulty": "Beginner",
                "duration": "20 Hours",
                "why_useful": "Validates cloud fundamentals and serverless services relevant to modern software applications.",
                "skills_improved": ["Cloud Compute", "Serverless", "Security"],
                "target_alignment": "Modern Backend Development",
                "official_url": "https://aws.amazon.com/certification/certified-cloud-practitioner/",
                "category": "recommended"
            }
        ]
        adv_certs = [
            {
                "id": "cert-se3",
                "name": "Oracle Certified Professional: Java / Python Developer",
                "provider": "Oracle",
                "difficulty": "Advanced",
                "duration": "50 Hours",
                "why_useful": "Demonstrates deep concurrency, data structures, and enterprise architecture mastery.",
                "skills_improved": ["Data Structures", "Concurrency", "Enterprise Patterns"],
                "target_alignment": f"Senior {role}",
                "official_url": "https://education.oracle.com/",
                "category": "advanced"
            }
        ]
        projects_beginner = [
            {
                "id": "proj-b1",
                "title": "Role-Based Authentication & User Management Service",
                "difficulty": "Beginner",
                "estimated_duration": "1-2 Weeks",
                "technologies": ["Python", "Flask", "JWT", "PostgreSQL"],
                "skills_demonstrated": ["JWT Authentication", "Password Hashing", "Database Relationships"],
                "real_world_problem": "Secure user access control and credential management is foundational to every web product.",
                "features": ["JWT access & refresh tokens", "Bcrypt password hashing", "Role-based access control (Admin, User)", "Profile management endpoints"],
                "folder_structure": "auth-service/\n├── auth/\n├── models/\n├── app.py\n└── requirements.txt",
                "deployment_suggestion": "Render / Vercel with cloud PostgreSQL",
                "resume_impact": "Developed a secure authentication service with JWT token verification and Bcrypt encryption in Python/Flask.",
                "why_build_this": "Proves essential web security and backend design fundamentals."
            },
            {
                "id": "proj-b2",
                "title": "Interactive Task Management API with Real-Time Validation",
                "difficulty": "Beginner",
                "estimated_duration": "1 Week",
                "technologies": ["JavaScript", "HTML/CSS", "Flask REST API"],
                "skills_demonstrated": ["REST API Integration", "Async Fetch", "DOM Manipulation"],
                "real_world_problem": "Interactive web dashboards require seamless frontend-backend API communication.",
                "features": ["CRUD task operations", "Filter by priority and completion", "Local storage state caching"],
                "folder_structure": "task-app/\n├── frontend/\n├── backend/\n└── README.md",
                "deployment_suggestion": "Static frontend on GitHub Pages with Render backend",
                "resume_impact": "Built a full-stack task manager implementing async RESTful API communication and state persistence.",
                "why_build_this": "Validates core full-stack communication."
            }
        ]
        projects_intermediate = [
            {
                "id": "proj-i1",
                "title": "CareerPilot AI — Resume Analysis & Assessment Platform",
                "difficulty": "Intermediate",
                "estimated_duration": "3 Weeks",
                "technologies": ["Python", "Flask", "Firebase Firestore", "Gemini AI"],
                "skills_demonstrated": ["AI Integration", "Document Processing", "Cloud NoSQL Database"],
                "real_world_problem": "Job candidates struggle to identify skill gaps and ATS compatibility for target roles.",
                "features": ["PDF resume parsing", "AI-powered skill gap extraction", "Interactive career assessment", "Real-time analytics dashboard"],
                "folder_structure": "careerpilot/\n├── backend/\n├── frontend/\n└── services/",
                "deployment_suggestion": "Containerized Flask app with Firebase Hosting",
                "resume_impact": "Engineered an AI career preparation platform that parses resumes, evaluates ATS compatibility, and personalizes skill development paths.",
                "why_build_this": "Combines full-stack architecture with production AI LLM service integration."
            },
            {
                "id": "proj-i2",
                "title": "Real-Time Collaborative Document Workspace",
                "difficulty": "Intermediate",
                "estimated_duration": "3 Weeks",
                "technologies": ["WebSockets", "Flask-SocketIO", "JavaScript", "Redis"],
                "skills_demonstrated": ["Bidirectional WebSockets", "Concurrency Control", "Redis Pub/Sub"],
                "real_world_problem": "Remote teams require simultaneous collaborative text editing without overwriting changes.",
                "features": ["Live multi-user text synchronization", "Cursor presence tracking", "Document revision history"],
                "folder_structure": "collab-editor/\n├── app/\n├── static/\n└── server.py",
                "deployment_suggestion": "Render with Redis Pub/Sub instance",
                "resume_impact": "Built a real-time collaborative editor utilizing WebSockets and Redis Pub/Sub for low-latency state synchronization across concurrent clients.",
                "why_build_this": "Demonstrates advanced real-time networking and concurrency management."
            },
            {
                "id": "proj-i3",
                "title": "Secure Payment & Subscription Billing Gateway",
                "difficulty": "Intermediate",
                "estimated_duration": "2-3 Weeks",
                "technologies": ["Python", "Stripe API", "Flask", "PostgreSQL"],
                "skills_demonstrated": ["Third-Party API Integration", "Webhook Handling", "Idempotency"],
                "real_world_problem": "SaaS applications require reliable, idempotent subscription billing and automated invoice reconciliation.",
                "features": ["Stripe checkout integration", "Webhook listener with signature verification", "Subscription tier upgrades/cancellations"],
                "folder_structure": "billing-gateway/\n├── billing/\n├── webhooks/\n└── app.py",
                "deployment_suggestion": "Cloud serverless function or containerized service",
                "resume_impact": "Integrated Stripe subscription billing with idempotent webhook handlers ensuring 100% financial transaction accuracy.",
                "why_build_this": "Proves your ability to handle mission-critical financial integrations."
            }
        ]
        projects_advanced = [
            {
                "id": "proj-a1",
                "title": "Scalable Microservices E-Commerce Backend with Distributed Tracing",
                "difficulty": "Advanced",
                "estimated_duration": "4-5 Weeks",
                "technologies": ["Docker", "Flask", "gRPC", "PostgreSQL", "OpenTelemetry"],
                "skills_demonstrated": ["Microservices Architecture", "gRPC Inter-Service RPC", "Distributed Tracing", "API Gateway"],
                "real_world_problem": "Monolithic architectures fail to scale independently under varying departmental traffic.",
                "features": ["Separate Catalog, Cart, and Order microservices", "gRPC high-throughput inter-service calls", "Distributed request tracing with OpenTelemetry", "Centralized API Gateway"],
                "folder_structure": "ecommerce-microservices/\n├── gateway/\n├── catalog_service/\n├── order_service/\n└── docker-compose.yml",
                "deployment_suggestion": "Kubernetes cluster or multi-host Docker deployment",
                "resume_impact": "Architected a microservices e-commerce system leveraging gRPC, Docker, and OpenTelemetry distributed tracing to achieve high horizontal scalability.",
                "why_build_this": "Directly proves enterprise-level distributed system design and observability."
            },
            {
                "id": "proj-a2",
                "title": "AI-Powered Real-Time Video & Voice Interview Proctoring System",
                "difficulty": "Advanced",
                "estimated_duration": "5 Weeks",
                "technologies": ["Python", "WebRTC", "OpenCV", "Flask", "TensorFlow / PyTorch"],
                "skills_demonstrated": ["Real-Time Video Streaming", "Computer Vision", "WebRTC Media Server"],
                "real_world_problem": "Remote hiring assessments require automated integrity checks and speech analysis.",
                "features": ["WebRTC peer connection streaming", "Face & gaze estimation pipeline", "Speech-to-text audio transcription", "Automated candidate assessment report"],
                "folder_structure": "proctor-system/\n├── pipeline/\n├── webrtc/\n└── app.py",
                "deployment_suggestion": "GPU-enabled Cloud instance with WebRTC STUN/TURN server",
                "resume_impact": "Developed an AI proctoring platform featuring WebRTC video streaming and OpenCV computer vision models to provide automated interview analytics.",
                "why_build_this": "A flagship portfolio piece combining deep computer vision, WebRTC streaming, and backend systems."
            }
        ]

    return {
        "target_company": company,
        "target_role": role,
        "career_value_summary": f"By completing the recommended {company}-aligned certifications and building these portfolio projects, you establish verified proof of required competencies for {role}.",
        "certifications": {
            "must_complete": must_certs,
            "recommended": rec_certs,
            "advanced": adv_certs
        },
        "projects": {
            "beginner": projects_beginner,
            "intermediate": projects_intermediate,
            "advanced": projects_advanced
        }
    }


def generate_personalized_recommendations(goal, profile, resume, assessment, learning_plan):
    """
    Main entry point for generating personalized certifications and portfolio projects.
    """
    company = goal.get("company_name", "Target Company")
    role = goal.get("job_role", "Software Engineer")
    exp_level = goal.get("experience_level", "Fresher")

    # Extract missing skills from Phase 4/5
    missing_skills = []
    verified_skills = []
    if learning_plan:
        for phase in learning_plan.get("phases", []):
            for sk in phase.get("skills", []):
                if sk.get("status") == "VERIFIED":
                    verified_skills.append(sk.get("name"))
                else:
                    missing_skills.append(sk.get("name"))

    if not is_gemini_configured or not genai_client:
        logger.info("Recommendation Service: Using rule-based fallback generator.")
        return generate_fallback_recommendations(goal, profile, resume, assessment, learning_plan)

    prompt = f"""
SYSTEM INSTRUCTION:
You are the Chief Technology Recruiter and Engineering Mentor at {company}.
Create an elite, actionable recommendation bundle for candidate preparing for the {role} position ({exp_level}).

CANDIDATE STARTING CONTEXT:
- Target Company: {company}
- Target Role: {role}
- Verified Candidate Skills: {', '.join(verified_skills) if verified_skills else 'None yet'}
- Missing Skills / Learning Gaps: {', '.join(missing_skills) if missing_skills else 'Standard role competencies'}

CRITICAL RULES:
1. Certifications:
   - Categorize into 'must_complete', 'recommended', and 'advanced'.
   - ONLY include verified, globally recognized certifications from official providers (e.g. Microsoft, AWS, Google Cloud, Linux Foundation, CNCF, Oracle, Cisco, IBM, Coursera).
   - Use ONLY official provider URLs (e.g. https://learn.microsoft.com/, https://aws.amazon.com/certification/, https://training.linuxfoundation.org/). Do NOT invent fake URLs.
2. Projects:
   - Recommend AT LEAST 2 Beginner, 3 Intermediate, and 2 Advanced projects.
   - Every project MUST directly address the missing skills and target company expectations.
   - Do NOT suggest generic projects like 'calculator' or 'simple todo'.
   - Provide concrete technical features, proposed folder structure, deployment advice, and a clear resume impact bullet point.

Return ONLY a valid JSON object matching this exact schema:
{{
  "target_company": "{company}",
  "target_role": "{role}",
  "career_value_summary": "Summary explaining how these certifications and projects maximize placement odds at {company}...",
  "certifications": {{
    "must_complete": [
      {{
        "id": "cert-1",
        "name": "Certification Title",
        "provider": "Microsoft",
        "difficulty": "Beginner",
        "duration": "15 Hours",
        "why_useful": "Why this certification is vital for {role} at {company}...",
        "skills_improved": ["Skill 1", "Skill 2"],
        "target_alignment": "{company} {role}",
        "official_url": "https://learn.microsoft.com/...",
        "category": "must_complete"
      }}
    ],
    "recommended": [],
    "advanced": []
  }},
  "projects": {{
    "beginner": [
      {{
        "id": "proj-b1",
        "title": "Project Name",
        "difficulty": "Beginner",
        "estimated_duration": "1-2 Weeks",
        "technologies": ["Python", "Flask", "Docker"],
        "skills_demonstrated": ["Docker", "REST APIs"],
        "real_world_problem": "Problem statement...",
        "features": ["Feature 1", "Feature 2"],
        "folder_structure": "project/\n├── app.py\n└── Dockerfile",
        "deployment_suggestion": "Render / Azure Container Apps",
        "resume_impact": "Resume bullet point...",
        "why_build_this": "Why this project bridges your skill gaps..."
      }}
    ],
    "intermediate": [],
    "advanced": []
  }}
}}
"""

    def parse_gemini_recs(text):
        cleaned = clean_json_text(text)
        data = json.loads(cleaned)
        if validate_recommendations_json(data):
            # Sanitize certification URLs
            for tier in ["must_complete", "recommended", "advanced"]:
                for cert in data["certifications"].get(tier, []):
                    cert["official_url"] = sanitize_official_url(cert.get("official_url"), cert.get("provider", "Microsoft"))
            return data
        return None

    try:
        raw_response = call_gemini_with_retry(genai_client, prompt, response_mime_type="application/json")
        if raw_response:
            parsed = parse_gemini_recs(raw_response)
            if parsed:
                return parsed
    except Exception as e:
        logger.error(f"Gemini recommendation generation error: {e}")

    logger.warning("Falling back to rule-based recommendation generator.")
    return generate_fallback_recommendations(goal, profile, resume, assessment, learning_plan)
