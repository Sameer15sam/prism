import axios from 'axios';
import type { ParseResponse, CompareResponse } from '../types/capability';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const api = axios.create({ baseURL: BASE_URL });

export async function parseLog(file: File): Promise<ParseResponse> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post<ParseResponse>('/parse', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
}

export async function compareLogs(
    dut: File,
    ref: File
): Promise<CompareResponse> {
    const form = new FormData();
    form.append('dut', dut);
    form.append('ref', ref);
    const { data } = await api.post<CompareResponse>('/compare', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
}
