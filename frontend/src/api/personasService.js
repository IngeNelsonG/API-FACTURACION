import { http } from './httpClient';

/** GET /personas → clientes (personas naturales) registrados */
export const getPersonas = () => http('/personas', { auth: false });
