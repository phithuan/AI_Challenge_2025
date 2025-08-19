-- Tạo bảng cho video
    CREATE TABLE IF NOT EXISTS videos (
        id SERIAL PRIMARY KEY,
        video_path VARCHAR(255) UNIQUE,
        title VARCHAR(255),
        description TEXT
);

-- Tạo bảng cho ánh xạ khung hình-video
    CREATE TABLE IF NOT EXISTS frame_mappings (
        frame_id SERIAL PRIMARY KEY,
        video_id INTEGER REFERENCES videos(id),
        frame_path VARCHAR(255),
        milvus_id BIGINT
);

ALTER TABLE videos
ADD CONSTRAINT unique_video_path UNIQUE (video_path);

ALTER TABLE frame_mappings
ADD CONSTRAINT unique_frame_path UNIQUE (frame_path);

SELECT * FROM frame_mappings;
SELECT * FROM videos;

SELECT * FROM frame_mappings WHERE frame_path LIKE '%L21_V001%';
SELECT * FROM videos WHERE video_path LIKE '%L21_V001%';

