-- AlsaniaMCP Telemetry System Database Schema
-- Activity logging and analytics for Echo visibility

-- Create telemetry schema
CREATE SCHEMA IF NOT EXISTS telemetry;

-- Activity Log - Captures every agent event and user API call
CREATE TABLE IF NOT EXISTS telemetry.activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Event Classification
    event_type VARCHAR(50) NOT NULL, -- 'api_call', 'agent_action', 'system_event', 'user_interaction'
    event_category VARCHAR(50) NOT NULL, -- 'memory', 'agent', 'auth', 'search', 'snapshot', 'chaos'
    event_action VARCHAR(100) NOT NULL, -- 'store', 'retrieve', 'create', 'delete', 'update', 'search'
    
    -- Source Information
    source_type VARCHAR(50) NOT NULL, -- 'user', 'agent', 'system', 'echo', 'chaos'
    source_id VARCHAR(255), -- user_id, agent_id, system_component
    source_ip INET,
    user_agent TEXT,
    
    -- Request/Response Data
    request_data JSONB DEFAULT '{}',
    response_data JSONB DEFAULT '{}',
    status_code INTEGER,
    error_message TEXT,
    
    -- Performance Metrics
    duration_ms INTEGER, -- Request duration in milliseconds
    memory_usage_mb FLOAT,
    cpu_usage_percent FLOAT,
    
    -- Context & Correlation
    session_id VARCHAR(255),
    correlation_id UUID,
    trace_id VARCHAR(255),
    parent_event_id UUID,
    
    -- Metadata
    api_key_id UUID,
    namespace VARCHAR(100),
    agent_type VARCHAR(50),
    endpoint VARCHAR(200),
    method VARCHAR(10),
    
    -- Indexing helpers
    date_partition DATE GENERATED ALWAYS AS (DATE(timestamp AT TIME ZONE 'UTC')) STORED,
    hour_partition INTEGER GENERATED ALWAYS AS (EXTRACT(hour FROM timestamp AT TIME ZONE 'UTC')) STORED
);

-- API Usage Analytics
CREATE TABLE IF NOT EXISTS telemetry.api_usage_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    hour INTEGER NOT NULL,
    
    -- API Key Information
    api_key_id UUID,
    api_key_tier VARCHAR(20),
    
    -- Usage Counters
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    
    -- Endpoint Breakdown
    memory_operations INTEGER DEFAULT 0,
    agent_operations INTEGER DEFAULT 0,
    search_operations INTEGER DEFAULT 0,
    snapshot_operations INTEGER DEFAULT 0,
    auth_operations INTEGER DEFAULT 0,
    
    -- Performance Metrics
    avg_response_time_ms FLOAT DEFAULT 0,
    max_response_time_ms INTEGER DEFAULT 0,
    min_response_time_ms INTEGER DEFAULT 0,
    
    -- Resource Usage
    total_memory_mb FLOAT DEFAULT 0,
    avg_cpu_percent FLOAT DEFAULT 0,
    
    -- Error Analysis
    error_4xx_count INTEGER DEFAULT 0,
    error_5xx_count INTEGER DEFAULT 0,
    timeout_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(date, hour, api_key_id)
);

-- Agent Performance Tracking
CREATE TABLE IF NOT EXISTS telemetry.agent_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Agent Information
    agent_id VARCHAR(255) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    agent_status VARCHAR(20) NOT NULL,
    
    -- Performance Metrics
    tasks_completed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    avg_task_duration_ms FLOAT DEFAULT 0,
    memory_usage_mb FLOAT DEFAULT 0,
    cpu_usage_percent FLOAT DEFAULT 0,
    
    -- Health Indicators
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    error_rate_percent FLOAT DEFAULT 0,
    uptime_seconds INTEGER DEFAULT 0,
    
    -- Task Queue Metrics
    pending_tasks INTEGER DEFAULT 0,
    processing_tasks INTEGER DEFAULT 0,
    
    -- Custom Metrics (agent-specific)
    custom_metrics JSONB DEFAULT '{}',
    
    -- Indexing helpers
    date_partition DATE GENERATED ALWAYS AS (DATE(timestamp AT TIME ZONE 'UTC')) STORED,
    hour_partition INTEGER GENERATED ALWAYS AS (EXTRACT(hour FROM timestamp AT TIME ZONE 'UTC')) STORED
);

-- System Health Metrics
CREATE TABLE IF NOT EXISTS telemetry.system_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Service Information
    service_name VARCHAR(100) NOT NULL,
    service_type VARCHAR(50) NOT NULL, -- 'core', 'agent', 'infrastructure', 'monitoring'
    
    -- Health Status
    status VARCHAR(20) NOT NULL, -- 'healthy', 'degraded', 'unhealthy', 'unknown'
    health_score FLOAT DEFAULT 0, -- 0-100
    
    -- Resource Metrics
    cpu_usage_percent FLOAT DEFAULT 0,
    memory_usage_mb FLOAT DEFAULT 0,
    disk_usage_percent FLOAT DEFAULT 0,
    network_io_mbps FLOAT DEFAULT 0,
    
    -- Service-Specific Metrics
    active_connections INTEGER DEFAULT 0,
    queue_depth INTEGER DEFAULT 0,
    response_time_ms FLOAT DEFAULT 0,
    error_rate_percent FLOAT DEFAULT 0,
    
    -- Database Metrics (for postgres/qdrant)
    db_connections INTEGER DEFAULT 0,
    db_query_time_ms FLOAT DEFAULT 0,
    db_size_mb FLOAT DEFAULT 0,
    
    -- Custom Metrics
    custom_metrics JSONB DEFAULT '{}',
    
    -- Indexing helpers
    date_partition DATE GENERATED ALWAYS AS (DATE(timestamp AT TIME ZONE 'UTC')) STORED,
    hour_partition INTEGER GENERATED ALWAYS AS (EXTRACT(hour FROM timestamp AT TIME ZONE 'UTC')) STORED
);

-- Chaos Testing Results
CREATE TABLE IF NOT EXISTS telemetry.chaos_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Chaos Event Information
    chaos_type VARCHAR(50) NOT NULL, -- 'latency', 'error', 'resource', 'network'
    target_service VARCHAR(100) NOT NULL,
    intensity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high'
    
    -- Event Details
    event_description TEXT,
    parameters JSONB DEFAULT '{}',
    duration_seconds INTEGER,
    
    -- Impact Assessment
    affected_requests INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    recovery_time_seconds INTEGER,
    
    -- Echo Response
    echo_detected BOOLEAN DEFAULT false,
    echo_response_time_seconds INTEGER,
    echo_mitigation_actions JSONB DEFAULT '{}',
    
    -- Results
    test_passed BOOLEAN,
    lessons_learned TEXT,
    improvements_identified JSONB DEFAULT '{}'
);

-- Create partitioned tables for better performance (by date)
-- Activity log partitioning
CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON telemetry.activity_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_log_event_type ON telemetry.activity_log(event_type);
CREATE INDEX IF NOT EXISTS idx_activity_log_source_id ON telemetry.activity_log(source_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_api_key ON telemetry.activity_log(api_key_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_correlation ON telemetry.activity_log(correlation_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_date_partition ON telemetry.activity_log(date_partition);

-- API usage stats indexes
CREATE INDEX IF NOT EXISTS idx_api_usage_date_hour ON telemetry.api_usage_stats(date, hour);
CREATE INDEX IF NOT EXISTS idx_api_usage_api_key ON telemetry.api_usage_stats(api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_tier ON telemetry.api_usage_stats(api_key_tier);

-- Agent metrics indexes
CREATE INDEX IF NOT EXISTS idx_agent_metrics_agent_id ON telemetry.agent_metrics(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_timestamp ON telemetry.agent_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_type ON telemetry.agent_metrics(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_date_partition ON telemetry.agent_metrics(date_partition);

-- System health indexes
CREATE INDEX IF NOT EXISTS idx_system_health_service ON telemetry.system_health(service_name);
CREATE INDEX IF NOT EXISTS idx_system_health_timestamp ON telemetry.system_health(timestamp);
CREATE INDEX IF NOT EXISTS idx_system_health_status ON telemetry.system_health(status);
CREATE INDEX IF NOT EXISTS idx_system_health_date_partition ON telemetry.system_health(date_partition);

-- Chaos events indexes
CREATE INDEX IF NOT EXISTS idx_chaos_events_timestamp ON telemetry.chaos_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_chaos_events_type ON telemetry.chaos_events(chaos_type);
CREATE INDEX IF NOT EXISTS idx_chaos_events_target ON telemetry.chaos_events(target_service);

-- Create views for common queries
CREATE OR REPLACE VIEW telemetry.daily_api_summary AS
SELECT 
    date_partition as date,
    api_key_id,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE status_code < 400) as successful_requests,
    COUNT(*) FILTER (WHERE status_code >= 400) as failed_requests,
    AVG(duration_ms) as avg_response_time,
    COUNT(DISTINCT source_id) as unique_users,
    COUNT(DISTINCT session_id) as unique_sessions
FROM telemetry.activity_log 
WHERE event_type = 'api_call'
GROUP BY date_partition, api_key_id;

CREATE OR REPLACE VIEW telemetry.agent_health_summary AS
SELECT 
    agent_id,
    agent_type,
    MAX(timestamp) as last_seen,
    AVG(cpu_usage_percent) as avg_cpu,
    AVG(memory_usage_mb) as avg_memory,
    AVG(error_rate_percent) as avg_error_rate,
    SUM(tasks_completed) as total_tasks_completed,
    SUM(tasks_failed) as total_tasks_failed
FROM telemetry.agent_metrics 
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY agent_id, agent_type;

COMMENT ON SCHEMA telemetry IS 'AlsaniaMCP Telemetry System - Comprehensive activity logging and analytics';
COMMENT ON TABLE telemetry.activity_log IS 'Captures every agent event and user API call for Echo visibility';
COMMENT ON TABLE telemetry.api_usage_stats IS 'Aggregated API usage statistics for analytics and billing';
COMMENT ON TABLE telemetry.agent_metrics IS 'Performance and health metrics for all agents';
COMMENT ON TABLE telemetry.system_health IS 'System-wide health and performance monitoring';
COMMENT ON TABLE telemetry.chaos_events IS 'Chaos testing events and Echo response tracking';
