import {
  CAMPAIGN_OBJECTIVES,
  CAMPAIGN_PLATFORMS,
  CAMPAIGN_STATUSES,
  CAMPAIGN_TONES,
} from '../constants/campaigns';

export const CampaignForm = ({
  values,
  onChange,
  onSubmit,
  onCancel,
  submitLabel,
  isSubmitting,
  errorMessage,
  showStatus = false,
}) => {
  const handleChange = (event) => {
    const { name, value } = event.target;
    onChange({ ...values, [name]: value });
  };

  return (
    <form className="campaign-form" onSubmit={onSubmit} noValidate>
      {errorMessage && (
        <div className="alert alert-error" role="alert">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <span>{errorMessage}</span>
        </div>
      )}

      <div className="campaign-form-grid">
        <div className="form-group">
          <label htmlFor="campaign-name" className="form-label">Campaign Name</label>
          <input
            id="campaign-name"
            name="name"
            type="text"
            className="form-input form-input-plain"
            value={values.name}
            onChange={handleChange}
            maxLength={150}
            required
            placeholder="Summer Sale"
          />
        </div>

        <div className="form-group">
          <label htmlFor="campaign-product" className="form-label">Product / Service</label>
          <input
            id="campaign-product"
            name="product_name"
            type="text"
            className="form-input form-input-plain"
            value={values.product_name}
            onChange={handleChange}
            maxLength={150}
            required
            placeholder="Wireless headphones"
          />
        </div>

        <div className="form-group form-span-2">
          <label htmlFor="campaign-description" className="form-label">Description</label>
          <textarea
            id="campaign-description"
            name="description"
            className="form-textarea"
            value={values.description}
            onChange={handleChange}
            rows={4}
            required
            placeholder="Describe the campaign message, offer, and creative direction."
          />
        </div>

        <div className="form-group form-span-2">
          <label htmlFor="campaign-audience" className="form-label">Target Audience</label>
          <textarea
            id="campaign-audience"
            name="target_audience"
            className="form-textarea"
            value={values.target_audience}
            onChange={handleChange}
            rows={3}
            required
            placeholder="Who should this campaign reach?"
          />
        </div>

        <div className="form-group">
          <label htmlFor="campaign-platform" className="form-label">Platform</label>
          <select
            id="campaign-platform"
            name="platform"
            className="form-select"
            value={values.platform}
            onChange={handleChange}
            required
          >
            {CAMPAIGN_PLATFORMS.map((platform) => (
              <option key={platform} value={platform}>{platform}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="campaign-objective" className="form-label">Campaign Objective</label>
          <select
            id="campaign-objective"
            name="objective"
            className="form-select"
            value={values.objective}
            onChange={handleChange}
            required
          >
            {CAMPAIGN_OBJECTIVES.map((objective) => (
              <option key={objective} value={objective}>{objective}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="campaign-tone" className="form-label">Tone</label>
          <select
            id="campaign-tone"
            name="tone"
            className="form-select"
            value={values.tone}
            onChange={handleChange}
            required
          >
            {CAMPAIGN_TONES.map((tone) => (
              <option key={tone} value={tone}>{tone}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="campaign-budget" className="form-label">
            Budget <span className="label-helper">(optional)</span>
          </label>
          <input
            id="campaign-budget"
            name="budget"
            type="number"
            min="0"
            step="0.01"
            className="form-input form-input-plain"
            value={values.budget}
            onChange={handleChange}
            placeholder="0.00"
          />
        </div>

        {showStatus && (
          <div className="form-group">
            <label htmlFor="campaign-status" className="form-label">Status</label>
            <select
              id="campaign-status"
              name="status"
              className="form-select"
              value={values.status}
              onChange={handleChange}
            >
              {CAMPAIGN_STATUSES.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </div>
        )}

        <div className="form-group form-span-2">
          <label htmlFor="campaign-keywords" className="form-label">
            Keywords <span className="label-helper">(optional)</span>
          </label>
          <textarea
            id="campaign-keywords"
            name="keywords"
            className="form-textarea"
            value={values.keywords}
            onChange={handleChange}
            rows={2}
            placeholder="summer, wireless, headphones"
          />
        </div>
      </div>

      <div className="campaign-form-actions">
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={isSubmitting}>
          {isSubmitting ? (
            <span className="btn-loading-state">
              <span className="mini-spinner"></span>
              <span>Saving...</span>
            </span>
          ) : (
            submitLabel
          )}
        </button>
      </div>
    </form>
  );
};

export default CampaignForm;
