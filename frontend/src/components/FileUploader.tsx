import { useRef, useState, DragEvent, ChangeEvent } from 'react';
import styles from './FileUploader.module.css';

interface Props {
    label: string;
    accept?: string;
    onFile: (file: File) => void;
    file?: File | null;
}

const FileUploader: React.FC<Props> = ({
    label,
    accept = '.txt,.log',
    onFile,
    file,
}) => {
    const inputRef = useRef<HTMLInputElement>(null);
    const [dragging, setDragging] = useState(false);

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setDragging(false);
        const dropped = e.dataTransfer.files[0];
        if (dropped) onFile(dropped);
    };

    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
        const selected = e.target.files?.[0];
        if (selected) onFile(selected);
    };

    return (
        <div
            id={`uploader-${label.toLowerCase().replace(/\s+/g, '-')}`}
            className={`${styles.zone} ${dragging ? styles.dragging : ''} ${file ? styles.filled : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        >
            <input
                ref={inputRef}
                type="file"
                accept={accept}
                style={{ display: 'none' }}
                onChange={handleChange}
            />
            <div className={styles.icon}>{file ? '📄' : '📂'}</div>
            <div className={styles.label}>{label}</div>
            {file ? (
                <div className={styles.filename}>{file.name}</div>
            ) : (
                <div className={styles.hint}>Drag & drop or click to browse</div>
            )}
        </div>
    );
};

export default FileUploader;
