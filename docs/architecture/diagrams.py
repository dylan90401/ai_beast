"""
AI Beast Architecture Diagrams.

Generates C4 model diagrams using the diagrams library.
Run with: python docs/architecture/diagrams.py

Requirements:
    pip install diagrams

This will generate PNG diagrams in docs/architecture/images/
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.custom import Custom
from diagrams.onprem.client import User
from diagrams.onprem.compute import Server
from diagrams.onprem.container import Docker
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.network import Nginx, Traefik
from diagrams.onprem.queue import RabbitMQ
from diagrams.programming.framework import FastAPI
from diagrams.programming.language import Python

# Output directory
OUTPUT_DIR = "docs/architecture/images"


def context_diagram():
    """
    C4 Level 1: System Context Diagram.
    
    Shows AI Beast system and its interactions with external systems.
    """
    with Diagram(
        "AI Beast - System Context",
        filename=f"{OUTPUT_DIR}/c4_context",
        show=False,
        direction="TB",
    ):
        user = User("User")
        
        with Cluster("AI Beast System"):
            ai_beast = Server("AI Beast")
        
        # External systems
        ollama_models = Server("Ollama\nModel Registry")
        hf_hub = Server("Hugging Face\nHub")
        
        # Relationships
        user >> Edge(label="Uses") >> ai_beast
        ai_beast >> Edge(label="Downloads models") >> ollama_models
        ai_beast >> Edge(label="Downloads embeddings") >> hf_hub


def container_diagram():
    """
    C4 Level 2: Container Diagram.
    
    Shows the high-level containers within AI Beast.
    """
    with Diagram(
        "AI Beast - Container Diagram",
        filename=f"{OUTPUT_DIR}/c4_containers",
        show=False,
        direction="TB",
    ):
        user = User("User")
        
        with Cluster("AI Beast"):
            with Cluster("Frontend"):
                dashboard = FastAPI("Dashboard\n(Quart)")
                webui = Server("Open WebUI")
            
            with Cluster("Core Services"):
                cli = Python("Beast CLI")
                api = FastAPI("API Server")
                
            with Cluster("AI Services"):
                ollama = Docker("Ollama\n(LLM)")
                qdrant = Docker("Qdrant\n(Vector DB)")
                
            with Cluster("Data Layer"):
                redis = Redis("Redis\n(Cache)")
                postgres = PostgreSQL("PostgreSQL\n(Metadata)")
                
            with Cluster("Monitoring"):
                prometheus = Prometheus("Prometheus")
                grafana = Grafana("Grafana")
        
        # User interactions
        user >> dashboard
        user >> webui
        user >> cli
        
        # Internal connections
        dashboard >> api
        webui >> ollama
        cli >> api
        
        api >> ollama
        api >> qdrant
        api >> redis
        
        ollama >> prometheus
        qdrant >> prometheus
        prometheus >> grafana


def component_diagram_core():
    """
    C4 Level 3: Component Diagram - Core.
    
    Shows components within the core services.
    """
    with Diagram(
        "AI Beast - Core Components",
        filename=f"{OUTPUT_DIR}/c4_components_core",
        show=False,
        direction="LR",
    ):
        with Cluster("modules/"):
            with Cluster("LLM"):
                llm_manager = Python("LLM Manager")
                ollama_client = Python("Ollama Client")
                
            with Cluster("RAG"):
                rag_engine = Python("RAG Engine")
                chunker = Python("Chunker")
                embeddings = Python("Embeddings")
                ingestor = Python("Parallel Ingestor")
                
            with Cluster("Security"):
                validators = Python("Validators")
                rate_limit = Python("Rate Limiter")
                circuit_breaker = Python("Circuit Breaker")
                
            with Cluster("Infrastructure"):
                health = Python("Health Checker")
                cache = Python("Request Cache")
                pool = Python("Connection Pool")
                events = Python("Event Bus")
        
        # Dependencies
        rag_engine >> chunker
        rag_engine >> embeddings
        ingestor >> chunker
        ingestor >> embeddings
        
        llm_manager >> ollama_client
        ollama_client >> circuit_breaker
        ollama_client >> rate_limit


def deployment_diagram():
    """
    C4 Level 4: Deployment Diagram.
    
    Shows how the system is deployed.
    """
    with Diagram(
        "AI Beast - Deployment",
        filename=f"{OUTPUT_DIR}/c4_deployment",
        show=False,
        direction="TB",
    ):
        with Cluster("Host Machine"):
            with Cluster("Docker Compose"):
                with Cluster("Core Stack"):
                    ollama = Docker("ollama:latest")
                    qdrant = Docker("qdrant/qdrant")
                    redis = Docker("redis:7-alpine")
                    
                with Cluster("Extensions"):
                    webui = Docker("open-webui")
                    n8n = Docker("n8n")
                    jupyter = Docker("jupyter")
                    
                with Cluster("Monitoring"):
                    prom = Docker("prometheus")
                    graf = Docker("grafana")
                    
                with Cluster("Networking"):
                    traefik = Traefik("traefik")
            
            with Cluster("Local Python"):
                beast = Python("beast CLI")
                dashboard = FastAPI("Dashboard")
        
        # Networking
        traefik >> ollama
        traefik >> webui
        traefik >> dashboard
        
        # Data connections
        beast >> ollama
        beast >> qdrant
        dashboard >> redis


def data_flow_diagram():
    """
    Data Flow Diagram for RAG Pipeline.
    """
    with Diagram(
        "AI Beast - RAG Data Flow",
        filename=f"{OUTPUT_DIR}/rag_dataflow",
        show=False,
        direction="LR",
    ):
        user = User("User")
        
        with Cluster("Ingestion"):
            docs = Server("Documents")
            chunker = Python("Chunker")
            embedder = Python("Embeddings")
            
        with Cluster("Storage"):
            qdrant = Docker("Qdrant")
            
        with Cluster("Query"):
            retriever = Python("Retriever")
            llm = Docker("Ollama")
            generator = Python("Generator")
        
        # Ingestion flow
        docs >> chunker >> embedder >> qdrant
        
        # Query flow
        user >> retriever >> qdrant
        retriever >> generator
        llm >> generator
        generator >> user


def generate_all():
    """Generate all architecture diagrams."""
    import os
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("Generating C4 diagrams...")
    
    context_diagram()
    print("  ✓ Context diagram")
    
    container_diagram()
    print("  ✓ Container diagram")
    
    component_diagram_core()
    print("  ✓ Component diagram (core)")
    
    deployment_diagram()
    print("  ✓ Deployment diagram")
    
    data_flow_diagram()
    print("  ✓ RAG data flow diagram")
    
    print(f"\nDiagrams saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    generate_all()
