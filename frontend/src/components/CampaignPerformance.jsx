import { useCallback, useEffect, useMemo, useState } from 'react';
import { campaignService, getApiErrorMessage } from '../api/campaignService';

const today = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};
const emptyForm = () => ({ date: today(), impressions: '', clicks: '', conversions: '', spend: '', revenue: '' });

const formatCount = (value) => Number(value || 0).toLocaleString();
const formatMoney = (value) => value === null || value === undefined
  ? 'Unavailable'
  : Number(value).toLocaleString(undefined, { style: 'currency', currency: 'USD' });
const formatPercent = (value) => value === null || value === undefined ? 'Unavailable' : `${Number(value).toFixed(2)}%`;

const SummaryCard = ({ label, value, note }) => (
  <article className="performance-summary-card">
    <span>{label}</span>
    <strong>{value}</strong>
    {note && <small>{note}</small>}
  </article>
);

export const CampaignPerformance = ({ campaignId }) => {
  const [form, setForm] = useState(emptyForm);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [analytics, setAnalytics] = useState(null);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [formError, setFormError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [saving, setSaving] = useState(false);

  const dateRange = useMemo(() => {
    const range = {};
    if (startDate) range.start_date = startDate;
    if (endDate) range.end_date = endDate;
    return range;
  }, [startDate, endDate]);

  const loadPerformance = useCallback(async (isCurrent = () => true) => {
    setLoading(true);
    setLoadError('');
    try {
      const [summary, history] = await Promise.all([
        campaignService.getCampaignPerformanceAnalytics(campaignId, dateRange),
        campaignService.getCampaignPerformance(campaignId, dateRange),
      ]);
      if (isCurrent()) {
        setAnalytics(summary);
        setRecords(history.records || []);
      }
    } catch (error) {
      if (isCurrent()) setLoadError(getApiErrorMessage(error, 'Unable to load campaign performance.'));
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [campaignId, dateRange]);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => loadPerformance(() => active));
    return () => { active = false; };
  }, [loadPerformance]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError('');
    setSuccessMessage('');
    const payload = {
      date: form.date,
      impressions: Number(form.impressions),
      clicks: Number(form.clicks),
      conversions: Number(form.conversions),
      spend: Number(form.spend),
      revenue: form.revenue === '' ? null : Number(form.revenue),
    };
    if (payload.clicks > payload.impressions) {
      setFormError('Clicks cannot exceed impressions.');
      return;
    }
    if (payload.conversions > payload.clicks) {
      setFormError('Conversions cannot exceed clicks.');
      return;
    }

    setSaving(true);
    try {
      await campaignService.recordCampaignPerformance(campaignId, payload);
      setForm(emptyForm());
      setSuccessMessage('Daily results recorded.');
      await loadPerformance();
    } catch (error) {
      setFormError(getApiErrorMessage(error, 'Unable to record daily campaign results.'));
    } finally {
      setSaving(false);
    }
  };

  const updateForm = (field) => (event) => setForm((previous) => ({ ...previous, [field]: event.target.value }));

  return (
    <section className="campaign-performance-section" aria-labelledby="campaign-performance-title">
      <div className="workspace-section-heading">
        <div>
          <p className="page-kicker">Historical results</p>
          <h2 id="campaign-performance-title">Campaign Performance</h2>
          <p className="performance-source-note">Based on manually entered campaign results. Campaign budget is planned and is not counted as spend.</p>
        </div>
      </div>

      <form className="performance-entry-form" onSubmit={handleSubmit}>
        <h3>Record daily results</h3>
        <div className="performance-form-grid">
          <label className="form-label">Date<input className="form-input" type="date" value={form.date} onChange={updateForm('date')} required /></label>
          <label className="form-label">Impressions<input className="form-input" type="number" min="0" step="1" value={form.impressions} onChange={updateForm('impressions')} required /></label>
          <label className="form-label">Clicks<input className="form-input" type="number" min="0" step="1" value={form.clicks} onChange={updateForm('clicks')} required /></label>
          <label className="form-label">Conversions<input className="form-input" type="number" min="0" step="1" value={form.conversions} onChange={updateForm('conversions')} required /></label>
          <label className="form-label">Actual spend (USD)<input className="form-input" type="number" min="0" step="0.01" value={form.spend} onChange={updateForm('spend')} required /></label>
          <label className="form-label">Revenue (USD, optional)<input className="form-input" type="number" min="0" step="0.01" value={form.revenue} onChange={updateForm('revenue')} /></label>
        </div>
        <div className="performance-form-footer">
          <p>One record per campaign per day. Revenue is needed to calculate ROI.</p>
          <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Record results'}</button>
        </div>
        {formError && <p className="alert alert-error" role="alert">{formError}</p>}
        {successMessage && <p className="performance-success" role="status">{successMessage}</p>}
      </form>

      <div className="performance-filter-row">
        <h3>Recorded performance</h3>
        <label>From <input className="form-input" type="date" value={startDate} max={endDate || undefined} onChange={(event) => setStartDate(event.target.value)} /></label>
        <label>To <input className="form-input" type="date" value={endDate} min={startDate || undefined} onChange={(event) => setEndDate(event.target.value)} /></label>
      </div>

      {loadError && <div className="alert alert-error" role="alert">{loadError} <button type="button" className="performance-retry" onClick={loadPerformance}>Try again</button></div>}
      {loading ? <p className="performance-loading" role="status">Loading recorded performance…</p> : !loadError && analytics && analytics.record_count === 0 ? (
        <div className="performance-empty-state">
          <h3>No daily results in this date range</h3>
          <p>Enter campaign results above to see historical totals and calculated metrics. No sample or platform data is shown.</p>
        </div>
      ) : !loadError && analytics && (
        <>
          <div className="performance-summary-grid" aria-label="Recorded totals and calculated historical metrics">
            <SummaryCard label="Impressions" value={formatCount(analytics.impressions)} note="Recorded total" />
            <SummaryCard label="Clicks" value={formatCount(analytics.clicks)} note="Recorded total" />
            <SummaryCard label="Conversions" value={formatCount(analytics.conversions)} note="Recorded total" />
            <SummaryCard label="Actual spend" value={formatMoney(analytics.spend)} note="Recorded total" />
            <SummaryCard label="Revenue" value={formatMoney(analytics.revenue)} note="Unavailable if any day is missing revenue" />
            <SummaryCard label="CTR" value={formatPercent(analytics.ctr_percent)} note="Clicks ÷ impressions" />
            <SummaryCard label="Conversion rate" value={formatPercent(analytics.conversion_rate_percent)} note="Conversions ÷ clicks" />
            <SummaryCard label="CPC" value={formatMoney(analytics.cpc)} note="Spend ÷ clicks" />
            <SummaryCard label="ROI" value={formatPercent(analytics.roi_percent)} note="(Revenue − spend) ÷ spend" />
          </div>
          <div className="performance-table-wrap">
            <table className="performance-table">
              <thead><tr><th>Date</th><th>Impressions</th><th>Clicks</th><th>Conversions</th><th>Spend</th><th>Revenue</th></tr></thead>
              <tbody>{records.map((record) => (
                <tr key={record.id}>
                  <td>{record.date}</td><td>{formatCount(record.impressions)}</td><td>{formatCount(record.clicks)}</td>
                  <td>{formatCount(record.conversions)}</td><td>{formatMoney(record.spend)}</td><td>{formatMoney(record.revenue)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
};

export default CampaignPerformance;
