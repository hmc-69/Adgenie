import { useState } from 'react';
import { campaignService, getApiErrorMessage } from '../api/campaignService';

const metric = (value) => value === null || value === undefined || !Number.isFinite(Number(value))
  ? 'Unavailable'
  : Number(value).toFixed(3);

const Evaluation = ({ label, result }) => (
  <div className="prediction-evaluation-target">
    <h4>{label}</h4>
    {result ? (
      <>
        <p>Selected: <strong>{result.selected_model}</strong></p>
        <p>Test MAE: {metric(result.test_mae)} percentage points · RMSE: {metric(result.test_rmse)} · R²: {metric(result.test_r2)}</p>
        <p>Dummy baseline MAE: {metric(result.baseline_test_mae)} · RMSE: {metric(result.baseline_test_rmse)} · R²: {metric(result.baseline_test_r2)}</p>
        {!result.meaningful_improvement_over_baseline && <p className="prediction-no-improvement">No meaningful improvement over the synthetic baseline was demonstrated.</p>}
      </>
    ) : <p>Evaluation metrics unavailable.</p>}
  </div>
);

export const CampaignPredictionResults = ({ prediction }) => (
  <div className="campaign-prediction-results" aria-label="Predicted performance results">
    <div className="prediction-warning" role="note">
      Experimental estimate trained on synthetic data. These values are not recorded campaign performance and are not validated for real-world accuracy.
    </div>
    <div className="prediction-result-heading">
      <h3>Predicted performance</h3>
      <span>Model {prediction.model_version}</span>
    </div>
    <div className="prediction-values-grid">
      <article className="prediction-value-card"><span>Predicted CTR</span><strong>{Number(prediction.predictions.ctr_percent).toFixed(2)}%</strong></article>
      <article className="prediction-value-card"><span>Predicted conversion rate</span><strong>{Number(prediction.predictions.conversion_rate_percent).toFixed(2)}%</strong></article>
    </div>
    <div className="prediction-evaluation">
      <div className="performance-subheading"><h3>Synthetic held-out evaluation</h3><span>MAE and RMSE are percentage points; R² is unitless.</span></div>
      <Evaluation label="CTR" result={prediction.evaluation?.ctr} />
      <Evaluation label="Conversion rate" result={prediction.evaluation?.conversion_rate} />
    </div>
  </div>
);

export const CampaignPerformancePrediction = ({ campaignId }) => {
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handlePredict = async () => {
    if (loading) return;
    setLoading(true);
    setErrorMessage('');
    try {
      const result = await campaignService.predictCampaignPerformance(campaignId);
      setPrediction(result);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to predict campaign performance.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="campaign-prediction-section" aria-labelledby="campaign-prediction-title">
      <div className="workspace-section-heading">
        <div>
          <p className="page-kicker">Experimental estimate</p>
          <h2 id="campaign-prediction-title">Campaign Performance Prediction</h2>
          <p className="prediction-intro">Uses the campaign setup fields already saved above. The model is an academic experiment trained and evaluated on synthetic data only.</p>
        </div>
      </div>
      <div className="prediction-warning" role="note">
        Synthetic-data experiment only. Predictions do not represent actual performance, do not use recorded results, and are not validated for real-world advertising outcomes.
      </div>
      {errorMessage && (
        <div className="alert alert-error" role="alert">
          <span>{errorMessage}</span>
          <button type="button" className="prediction-retry" onClick={handlePredict} disabled={loading}>Retry prediction</button>
        </div>
      )}
      <div className="prediction-action-row">
        {!prediction && !loading && !errorMessage && <p>No prediction has been requested for this campaign.</p>}
        <button type="button" className="btn-primary" onClick={handlePredict} disabled={loading}>
          {loading ? 'Predicting…' : prediction ? 'Predict again' : 'Predict Performance'}
        </button>
      </div>
      {loading && <p className="prediction-loading" role="status">Loading the local prediction model…</p>}
      {prediction && <CampaignPredictionResults prediction={prediction} />}
    </section>
  );
};

export default CampaignPerformancePrediction;
