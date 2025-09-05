-- AlsaniaMCP Echo System Database Schema
-- Persistent Echo Memory and State Management

-- Create echo-system schema
CREATE SCHEMA IF NOT EXISTS echo_system;

-- Echo Core State Table
CREATE TABLE IF NOT EXISTS echo_system.echo_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    echo_id VARCHAR(255) NOT NULL,
    state_type VARCHAR(50) NOT NULL, -- 'memory', 'learning', 'decision', 'integration'
    state_data JSONB NOT NULL,
    context JSONB DEFAULT '{}',
    confidence_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true
);

-- Echo Memory Summaries
CREATE TABLE IF NOT EXISTS echo_system.echo_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    echo_id VARCHAR(255) NOT NULL,
    summary_type VARCHAR(50) NOT NULL, -- 'daily', 'weekly', 'event', 'learning'
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    importance_score FLOAT DEFAULT 0.0,
    related_events UUID[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE
);

-- Echo Event History
CREATE TABLE IF NOT EXISTS echo_system.echo_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    echo_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL, -- 'agent_spawn', 'system_integration', 'learning_update', 'decision_made'
    event_source VARCHAR(100) NOT NULL, -- 'mcp', 'agent', 'telemetry', 'chaos', 'user'
    event_data JSONB NOT NULL,
    impact_level VARCHAR(20) DEFAULT 'low', -- 'low', 'medium', 'high', 'critical'
    correlation_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    is_processed BOOLEAN DEFAULT false
);

-- Echo Learning Progress
CREATE TABLE IF NOT EXISTS echo_system.echo_learning (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    echo_id VARCHAR(255) NOT NULL,
    learning_type VARCHAR(50) NOT NULL, -- 'pattern', 'optimization', 'adaptation', 'prediction'
    subject VARCHAR(200) NOT NULL,
    before_state JSONB,
    after_state JSONB,
    improvement_metrics JSONB DEFAULT '{}',
    confidence_change FLOAT DEFAULT 0.0,
    validation_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    validated_at TIMESTAMP WITH TIME ZONE
);

-- Echo Integration Points
CREATE TABLE IF NOT EXISTS echo_system.echo_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    echo_id VARCHAR(255) NOT NULL,
    integration_type VARCHAR(50) NOT NULL, -- 'mcp', 'agent', 'vscode', 'telemetry', 'dashboard'
    service_name VARCHAR(100) NOT NULL,
    service_url VARCHAR(500),
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'inactive', 'error', 'maintenance'
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    configuration JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent Registry (Echo-managed agents)
CREATE TABLE IF NOT EXISTS echo_system.agent_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(255) UNIQUE NOT NULL,
    agent_type VARCHAR(50) NOT NULL, -- 'cypher', 'scribe', 'sentinel', 'custom'
    agent_role VARCHAR(200) NOT NULL,
    namespace VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'spawning', -- 'spawning', 'active', 'paused', 'destroyed', 'error'
    capabilities TEXT[] DEFAULT '{}',
    tools TEXT[] DEFAULT '{}',
    data_sources TEXT[] DEFAULT '{}',
    parent_agent_id VARCHAR(255),
    clone_generation INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    destroyed_at TIMESTAMP WITH TIME ZONE,
    configuration JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}'
);

-- Task Queue for Agent Communications
CREATE TABLE IF NOT EXISTS echo_system.task_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) UNIQUE NOT NULL,
    source_agent_id VARCHAR(255),
    target_agent_id VARCHAR(255),
    task_type VARCHAR(50) NOT NULL, -- 'index', 'summarize', 'test', 'analyze', 'monitor'
    priority INTEGER DEFAULT 5, -- 1-10, 10 = highest
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'assigned', 'processing', 'completed', 'failed'
    assigned_to VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    assigned_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    result JSONB,
    error_message TEXT
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_echo_state_echo_id ON echo_system.echo_state(echo_id);
CREATE INDEX IF NOT EXISTS idx_echo_state_type ON echo_system.echo_state(state_type);
CREATE INDEX IF NOT EXISTS idx_echo_state_created_at ON echo_system.echo_state(created_at);

CREATE INDEX IF NOT EXISTS idx_echo_summaries_echo_id ON echo_system.echo_summaries(echo_id);
CREATE INDEX IF NOT EXISTS idx_echo_summaries_type ON echo_system.echo_summaries(summary_type);
CREATE INDEX IF NOT EXISTS idx_echo_summaries_created_at ON echo_system.echo_summaries(created_at);

CREATE INDEX IF NOT EXISTS idx_echo_events_echo_id ON echo_system.echo_events(echo_id);
CREATE INDEX IF NOT EXISTS idx_echo_events_type ON echo_system.echo_events(event_type);
CREATE INDEX IF NOT EXISTS idx_echo_events_source ON echo_system.echo_events(event_source);
CREATE INDEX IF NOT EXISTS idx_echo_events_created_at ON echo_system.echo_events(created_at);
CREATE INDEX IF NOT EXISTS idx_echo_events_correlation ON echo_system.echo_events(correlation_id);

CREATE INDEX IF NOT EXISTS idx_echo_learning_echo_id ON echo_system.echo_learning(echo_id);
CREATE INDEX IF NOT EXISTS idx_echo_learning_type ON echo_system.echo_learning(learning_type);
CREATE INDEX IF NOT EXISTS idx_echo_learning_created_at ON echo_system.echo_learning(created_at);

CREATE INDEX IF NOT EXISTS idx_echo_integrations_echo_id ON echo_system.echo_integrations(echo_id);
CREATE INDEX IF NOT EXISTS idx_echo_integrations_type ON echo_system.echo_integrations(integration_type);
CREATE INDEX IF NOT EXISTS idx_echo_integrations_status ON echo_system.echo_integrations(status);

CREATE INDEX IF NOT EXISTS idx_agent_registry_agent_id ON echo_system.agent_registry(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_registry_type ON echo_system.agent_registry(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_registry_status ON echo_system.agent_registry(status);
CREATE INDEX IF NOT EXISTS idx_agent_registry_namespace ON echo_system.agent_registry(namespace);

CREATE INDEX IF NOT EXISTS idx_task_queue_task_id ON echo_system.task_queue(task_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_status ON echo_system.task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_queue_priority ON echo_system.task_queue(priority);
CREATE INDEX IF NOT EXISTS idx_task_queue_target_agent ON echo_system.task_queue(target_agent_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_created_at ON echo_system.task_queue(created_at);

-- Insert initial Echo Core state
INSERT INTO echo_system.echo_state (echo_id, state_type, state_data, context)
VALUES (
    'echo-core-001',
    'initialization',
    '{"status": "initializing", "version": "1.0.0", "capabilities": ["orchestration", "learning", "integration"]}',
    jsonb_build_object('deployment', 'docker', 'environment', 'production', 'initialized_at', NOW()::text)
) ON CONFLICT DO NOTHING;

-- Insert initial integration points
INSERT INTO echo_system.echo_integrations (echo_id, integration_type, service_name, service_url, configuration)
VALUES 
    ('echo-core-001', 'mcp', 'alsaniamcp-backend', 'http://backend:8050', '{"api_version": "v1", "auth_required": true}'),
    ('echo-core-001', 'telemetry', 'alsaniamcp-telemetry', 'http://telemetry:8070', '{"batch_size": 1000, "flush_interval": 30}'),
    ('echo-core-001', 'agent', 'agent-registry', 'http://agent-registry:8080', '{"heartbeat_interval": 30, "timeout": 300}'),
    ('echo-core-001', 'chaos', 'chaos-framework', 'http://chaos-framework:8090', '{"mode": "controlled", "intensity": "low"}')
ON CONFLICT DO NOTHING;

COMMENT ON SCHEMA echo_system IS 'AlsaniaMCP Echo System - Persistent orchestration layer for continuous learning and evolution';
COMMENT ON TABLE echo_system.echo_state IS 'Core state management for Echo intelligence system';
COMMENT ON TABLE echo_system.echo_summaries IS 'Periodic summaries and insights generated by Echo';
COMMENT ON TABLE echo_system.echo_events IS 'Event history for Echo decision making and learning';
COMMENT ON TABLE echo_system.echo_learning IS 'Learning progress and adaptation tracking';
COMMENT ON TABLE echo_system.echo_integrations IS 'Integration points with ecosystem components';
COMMENT ON TABLE echo_system.agent_registry IS 'Registry of Echo-managed specialized agents';
COMMENT ON TABLE echo_system.task_queue IS 'Task communication system between agents';
