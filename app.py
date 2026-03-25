/* --- GRADE DE ANÚNCIOS (CARDS) --- */
.listing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
  margin-top: 24px;
}

.listing-card {
  background: #ffffff;
  border: 1px solid #dde3ea;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.04);
  transition: all 0.2s ease;
}

.listing-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 28px rgba(16, 24, 40, 0.12);
  border-color: #516b93;
}

/* Cabeçalho do Card */
.card-header h3 {
  margin: 0;
  font-size: 20px;
  color: #12284a;
}
.card-header .version {
  display: block;
  font-size: 14px;
  color: #5b6779;
  margin-top: 4px;
  height: 40px; /* Mantém o alinhamento mesmo se o texto for longo */
}

/* Preço */
.price-tag {
  font-size: 28px;
  font-weight: 800;
  color: #0f6b42; /* Verde escuro */
  margin: 16px 0;
}

/* Detalhes (Ano, KM, Local) */
.car-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #334155;
}
.car-details .full-width {
  grid-column: span 2;
  color: #5b6779;
}

/* Badges / Etiquetas */
.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 24px;
}
.tag {
  background: #edf1f6;
  color: #12284a;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}
.tag.new-tag {
  background: #dcfce7;
  color: #166534;
}

/* Botões do Card */
.card-actions {
  margin-top: auto;
  display: flex;
  gap: 12px;
}
.btn-anuncio {
  flex: 1;
  background: #0f213f;
  color: white;
  text-align: center;
  padding: 12px;
  border-radius: 10px;
  text-decoration: none;
  font-weight: bold;
  font-size: 14px;
}
.btn-anuncio:hover { background: #1a365d; }

.btn-loja {
  flex: 1;
  background: #f1f5f9;
  color: #334155;
  text-align: center;
  padding: 12px;
  border-radius: 10px;
  text-decoration: none;
  font-weight: bold;
  font-size: 14px;
}
.btn-loja:hover { background: #e2e8f0; }

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
  color: #5b6779;
  font-size: 18px;
  background: #f8fafc;
  border-radius: 12px;
}
