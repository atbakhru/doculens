-- Initial PostgreSQL schema. Apply once on an empty database.

CREATE TABLE upload_batches (
	id VARCHAR(32) NOT NULL,
	tenant VARCHAR(100) NOT NULL,
	name VARCHAR(160) NOT NULL,
	created_at FLOAT NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE TABLE cluster_runs (
	id VARCHAR(32) NOT NULL,
	batch_id VARCHAR(32) NOT NULL,
	model_version VARCHAR(80) NOT NULL,
	eps FLOAT NOT NULL,
	min_samples INTEGER NOT NULL,
	created_at FLOAT NOT NULL,
	status VARCHAR(20) NOT NULL,
	members JSON NOT NULL,
	names JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(batch_id) REFERENCES upload_batches (id)
)

;

CREATE TABLE documents (
	id VARCHAR(32) NOT NULL,
	batch_id VARCHAR(32) NOT NULL,
	filename VARCHAR(200) NOT NULL,
	mime VARCHAR(80) NOT NULL,
	size INTEGER NOT NULL,
	object_key VARCHAR(300) NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	status VARCHAR(30) NOT NULL,
	attempts INTEGER NOT NULL,
	error VARCHAR(300),
	page_count INTEGER NOT NULL,
	processed_pages INTEGER NOT NULL,
	updated_at FLOAT NOT NULL,
	available_at FLOAT NOT NULL,
	lease_token VARCHAR(32),
	created_at FLOAT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(batch_id) REFERENCES upload_batches (id)
)

;

CREATE TABLE pages (
	id VARCHAR(32) NOT NULL,
	document_id VARCHAR(32) NOT NULL,
	page_no INTEGER NOT NULL,
	width INTEGER NOT NULL,
	height INTEGER NOT NULL,
	image_key VARCHAR(300) NOT NULL,
	thumbnail_key VARCHAR(300) NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	phash VARCHAR(16) NOT NULL,
	model_version VARCHAR(80) NOT NULL,
	embedding JSON NOT NULL,
	duration_ms FLOAT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (document_id, page_no),
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

;
CREATE INDEX ix_upload_batches_tenant ON upload_batches (tenant);
CREATE INDEX ix_cluster_runs_batch_id ON cluster_runs (batch_id);
CREATE INDEX ix_documents_status ON documents (status);
CREATE INDEX ix_documents_batch_id ON documents (batch_id);
CREATE INDEX ix_pages_document_id ON pages (document_id);
CREATE INDEX ix_pages_sha256 ON pages (sha256);
