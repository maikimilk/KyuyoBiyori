import { useState } from 'react';
import Layout from '../components/Layout';

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/payslip/upload', { method: 'POST', body: formData });
    if (res.ok) {
      setMessage('アップロードしました');
    } else {
      setMessage('アップロード失敗');
    }
  };

  return (
    <Layout>
      <h1>明細アップロード</h1>
      <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
      <button onClick={handleUpload}>送信</button>
      <p>{message}</p>
    </Layout>
  );
}
