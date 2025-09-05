-- AlsaniaMCP Database Initialization Script
-- This script sets up the initial database schema for the Alsania Memory Control Plane

-- Create database if it doesn't exist (handled by POSTGRES_DB env var)
-- CREATE DATABASE IF NOT EXISTS mem0;

-- Connect to the mem0 database
\c mem0;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS alsania;
CREATE SCHEMA IF NOT EXISTS memory;
CREATE SCHEMA IF NOT EXISTS forensics;
CREATE SCHEMA IF NOT EXISTS agents;

-- Set search path
SET search_path TO alsania, memory, forensics, agents, public;

-- Memory storage table
CREATE TABLE IF NOT EXISTS memory.memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    source VARCHAR(255) DEFAULT 'unknown',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    hash VARCHAR(128) UNIQUE,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[]
);

-- Forensic logs table
CREATE TABLE IF NOT EXISTS forensics.access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID REFERENCES memory.memories(id),
    action VARCHAR(50) NOT NULL,
    user_agent TEXT,
    ip_address INET,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Agent state table
CREATE TABLE IF NOT EXISTS agents.agent_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(255) NOT NULL UNIQUE,
    state JSONB NOT NULL DEFAULT '{}',
    last_reflection TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Snapshots table
CREATE TABLE IF NOT EXISTS memory.snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_path TEXT NOT NULL,
    hash VARCHAR(128) UNIQUE,
    size_bytes BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memory.memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_source ON memory.memories(source);
CREATE INDEX IF NOT EXISTS idx_memories_hash ON memory.memories(hash);
CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON forensics.access_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_access_logs_memory_id ON forensics.access_logs(memory_id);
CREATE INDEX IF NOT EXISTS idx_agent_states_name ON agents.agent_states(agent_name);
CREATE INDEX IF NOT EXISTS idx_snapshots_created_at ON memory.snapshots(created_at);

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_memories_updated_at BEFORE UPDATE ON memory.memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agent_states_updated_at BEFORE UPDATE ON agents.agent_states
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert initial agent state for Echo
INSERT INTO agents.agent_states (agent_name, state, last_reflection) 
VALUES (
    'echo',
    '{"status": "initializing", "version": "1.2", "capabilities": ["memory", "reflection", "analysis"]}',
    NOW()
) ON CONFLICT (agent_name) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA memory TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA forensics TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA agents TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA memory TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA forensics TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA agents TO postgres;

COMMIT;
