/**
 * frontend/pages/RLModelPage.ts
 * RL Model Health, Metrics, and Prediction Interface
 */

import type { ModelMetrics, PredictionResult } from '../types';

export function renderRLModelPage(
    metrics: ModelMetrics | null
): HTMLElement {
    const page = document.createElement('div');
    page.className = 'main-content';

    const metricsHtml = metrics ? `
        <!-- Performance Metrics Section -->
        <div style="margin-bottom: 32px;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid rgba(0,0,0,0.1);">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="20" x2="12" y2="10"></line>
                    <line x1="18" y1="20" x2="18" y2="4"></line>
                    <line x1="6" y1="20" x2="6" y2="16"></line>
                </svg>
                <h3 style="margin: 0; font-size: 1.25rem; font-weight: 600; color: #000;">Performance Metrics</h3>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
                <div style="background: linear-gradient(135deg, rgba(40, 167, 69, 0.15) 0%, rgba(40, 167, 69, 0.05) 100%); border: 1px solid rgba(40, 167, 69, 0.3); border-radius: 16px; padding: 24px; transition: all 0.3s ease; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: -20px; right: -20px; width: 100px; height: 100px; background: radial-gradient(circle, rgba(40, 167, 69, 0.2) 0%, transparent 70%); border-radius: 50%;"></div>
                    <div style="display: flex; align-items: center; gap: 16px; position: relative; z-index: 1;">
                        <div style="width: 56px; height: 56px; background: rgba(40, 167, 69, 0.2); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <circle cx="12" cy="12" r="6"></circle>
                                <circle cx="12" cy="12" r="2"></circle>
                            </svg>
                        </div>
                        <div style="flex: 1;">
                            <p style="margin: 0 0 6px 0; font-size: 0.875rem; color: rgba(0,0,0,0.6); font-weight: 500;">Accuracy</p>
                            <p style="margin: 0; font-size: 2rem; font-weight: 700; color: #28a745; line-height: 1;">${(metrics.accuracy * 100).toFixed(2)}%</p>
                        </div>
                    </div>
                </div>

                <div style="background: linear-gradient(135deg, rgba(13, 110, 253, 0.15) 0%, rgba(13, 110, 253, 0.05) 100%); border: 1px solid rgba(13, 110, 253, 0.3); border-radius: 16px; padding: 24px; transition: all 0.3s ease; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: -20px; right: -20px; width: 100px; height: 100px; background: radial-gradient(circle, rgba(13, 110, 253, 0.2) 0%, transparent 70%); border-radius: 50%;"></div>
                    <div style="display: flex; align-items: center; gap: 16px; position: relative; z-index: 1;">
                        <div style="width: 56px; height: 56px; background: rgba(13, 110, 253, 0.2); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#0d6efd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <line x1="12" y1="2" x2="12" y2="6"></line>
                                <line x1="12" y1="18" x2="12" y2="22"></line>
                                <line x1="2" y1="12" x2="6" y2="12"></line>
                                <line x1="18" y1="12" x2="22" y2="12"></line>
                            </svg>
                        </div>
                        <div style="flex: 1;">
                            <p style="margin: 0 0 6px 0; font-size: 0.875rem; color: rgba(0,0,0,0.6); font-weight: 500;">Precision</p>
                            <p style="margin: 0; font-size: 2rem; font-weight: 700; color: #0d6efd; line-height: 1;">${(metrics.precision_macro * 100).toFixed(2)}%</p>
                        </div>
                    </div>
                </div>

                <div style="background: linear-gradient(135deg, rgba(253, 126, 20, 0.15) 0%, rgba(253, 126, 20, 0.05) 100%); border: 1px solid rgba(253, 126, 20, 0.3); border-radius: 16px; padding: 24px; transition: all 0.3s ease; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: -20px; right: -20px; width: 100px; height: 100px; background: radial-gradient(circle, rgba(253, 126, 20, 0.2) 0%, transparent 70%); border-radius: 50%;"></div>
                    <div style="display: flex; align-items: center; gap: 16px; position: relative; z-index: 1;">
                        <div style="width: 56px; height: 56px; background: rgba(253, 126, 20, 0.2); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fd7e14" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="11" cy="11" r="8"></circle>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                                <line x1="11" y1="8" x2="11" y2="14"></line>
                                <line x1="8" y1="11" x2="14" y2="11"></line>
                            </svg>
                        </div>
                        <div style="flex: 1;">
                            <p style="margin: 0 0 6px 0; font-size: 0.875rem; color: rgba(0,0,0,0.6); font-weight: 500;">Recall</p>
                            <p style="margin: 0; font-size: 2rem; font-weight: 700; color: #fd7e14; line-height: 1;">${(metrics.recall_macro * 100).toFixed(2)}%</p>
                        </div>
                    </div>
                </div>

                <div style="background: linear-gradient(135deg, rgba(255, 193, 7, 0.15) 0%, rgba(255, 193, 7, 0.05) 100%); border: 1px solid rgba(255, 193, 7, 0.3); border-radius: 16px; padding: 24px; transition: all 0.3s ease; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: -20px; right: -20px; width: 100px; height: 100px; background: radial-gradient(circle, rgba(255, 193, 7, 0.2) 0%, transparent 70%); border-radius: 50%;"></div>
                    <div style="display: flex; align-items: center; gap: 16px; position: relative; z-index: 1;">
                        <div style="width: 56px; height: 56px; background: rgba(255, 193, 7, 0.2); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ffc107" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M12 2v4"></path>
                                <path d="M12 18v4"></path>
                                <path d="M4.93 4.93l2.83 2.83"></path>
                                <path d="M16.24 16.24l2.83 2.83"></path>
                                <path d="M2 12h4"></path>
                                <path d="M18 12h4"></path>
                                <path d="M4.93 19.07l2.83-2.83"></path>
                                <path d="M16.24 7.76l2.83-2.83"></path>
                            </svg>
                        </div>
                        <div style="flex: 1;">
                            <p style="margin: 0 0 6px 0; font-size: 0.875rem; color: rgba(0,0,0,0.6); font-weight: 500;">F1 Score</p>
                            <p style="margin: 0; font-size: 2rem; font-weight: 700; color: #d39e00; line-height: 1;">${(metrics.f1_macro * 100).toFixed(2)}%</p>
                        </div>
                    </div>
                </div>

                <div style="background: linear-gradient(135deg, rgba(111, 66, 193, 0.15) 0%, rgba(111, 66, 193, 0.05) 100%); border: 1px solid rgba(111, 66, 193, 0.3); border-radius: 16px; padding: 24px; transition: all 0.3s ease; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: -20px; right: -20px; width: 100px; height: 100px; background: radial-gradient(circle, rgba(111, 66, 193, 0.2) 0%, transparent 70%); border-radius: 50%;"></div>
                    <div style="display: flex; align-items: center; gap: 16px; position: relative; z-index: 1;">
                        <div style="width: 56px; height: 56px; background: rgba(111, 66, 193, 0.2); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6f42c1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
                                <polyline points="17 6 23 6 23 12"></polyline>
                            </svg>
                        </div>
                        <div style="flex: 1;">
                            <p style="margin: 0 0 6px 0; font-size: 0.875rem; color: rgba(0,0,0,0.6); font-weight: 500;">ROC AUC</p>
                            <p style="margin: 0; font-size: 2rem; font-weight: 700; color: #6f42c1; line-height: 1;">${(metrics.roc_auc * 100).toFixed(2)}%</p>
                        </div>
                    </div>
                </div>

                <div style="background: linear-gradient(135deg, rgba(220, 53, 69, 0.15) 0%, rgba(220, 53, 69, 0.05) 100%); border: 1px solid rgba(220, 53, 69, 0.3); border-radius: 16px; padding: 24px; transition: all 0.3s ease; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: -20px; right: -20px; width: 100px; height: 100px; background: radial-gradient(circle, rgba(220, 53, 69, 0.2) 0%, transparent 70%); border-radius: 50%;"></div>
                    <div style="display: flex; align-items: center; gap: 16px; position: relative; z-index: 1;">
                        <div style="width: 56px; height: 56px; background: rgba(220, 53, 69, 0.2); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#dc3545" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="12" y1="3" x2="12" y2="21"></line>
                                <path d="M8 9l4-4 4 4"></path>
                                <path d="M16 15l-4 4-4-4"></path>
                            </svg>
                        </div>
                        <div style="flex: 1;">
                            <p style="margin: 0 0 6px 0; font-size: 0.875rem; color: rgba(0,0,0,0.6); font-weight: 500;">Balanced Accuracy</p>
                            <p style="margin: 0; font-size: 2rem; font-weight: 700; color: #dc3545; line-height: 1;">${(metrics.balanced_accuracy * 100).toFixed(2)}%</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Confusion Matrix Stats Section -->
        <div>
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid rgba(0,0,0,0.1);">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="7" height="7"></rect>
                    <rect x="14" y="3" width="7" height="7"></rect>
                    <rect x="14" y="14" width="7" height="7"></rect>
                    <rect x="3" y="14" width="7" height="7"></rect>
                </svg>
                <h3 style="margin: 0; font-size: 1.25rem; font-weight: 600; color: #000;">Confusion Matrix Statistics</h3>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;">
                <div style="background: #fff; border: 1px solid rgba(0,0,0,0.1); border-radius: 12px; padding: 20px; text-align: center; transition: all 0.3s ease;">
                    <div style="width: 48px; height: 48px; background: rgba(100,100,100,0.1); border-radius: 10px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="rgba(0,0,0,0.6)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                        </svg>
                    </div>
                    <p style="margin: 0 0 8px 0; font-size: 0.813rem; color: rgba(0,0,0,0.6); font-weight: 500;">Total Predictions</p>
                    <p style="margin: 0; font-size: 1.75rem; font-weight: 700; color: #000;">${metrics.total_predictions.toLocaleString()}</p>
                </div>

                <div style="background: linear-gradient(135deg, rgba(40, 167, 69, 0.1) 0%, rgba(40, 167, 69, 0.02) 100%); border: 1px solid rgba(40, 167, 69, 0.3); border-radius: 12px; padding: 20px; text-align: center; transition: all 0.3s ease;">
                    <div style="width: 48px; height: 48px; background: rgba(40, 167, 69, 0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                            <polyline points="22 4 12 14.01 9 11.01"></polyline>
                        </svg>
                    </div>
                    <p style="margin: 0 0 8px 0; font-size: 0.813rem; color: rgba(40, 167, 69, 0.9); font-weight: 500;">True Positives</p>
                    <p style="margin: 0; font-size: 1.75rem; font-weight: 700; color: #28a745;">${metrics.true_positives.toLocaleString()}</p>
                </div>

                <div style="background: linear-gradient(135deg, rgba(40, 167, 69, 0.1) 0%, rgba(40, 167, 69, 0.02) 100%); border: 1px solid rgba(40, 167, 69, 0.3); border-radius: 12px; padding: 20px; text-align: center; transition: all 0.3s ease;">
                    <div style="width: 48px; height: 48px; background: rgba(40, 167, 69, 0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                            <path d="M9 12l2 2 4-4"></path>
                        </svg>
                    </div>
                    <p style="margin: 0 0 8px 0; font-size: 0.813rem; color: rgba(40, 167, 69, 0.9); font-weight: 500;">True Negatives</p>
                    <p style="margin: 0; font-size: 1.75rem; font-weight: 700; color: #28a745;">${metrics.true_negatives.toLocaleString()}</p>
                </div>

                <div style="background: linear-gradient(135deg, rgba(253, 126, 20, 0.1) 0%, rgba(253, 126, 20, 0.02) 100%); border: 1px solid rgba(253, 126, 20, 0.3); border-radius: 12px; padding: 20px; text-align: center; transition: all 0.3s ease;">
                    <div style="width: 48px; height: 48px; background: rgba(253, 126, 20, 0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fd7e14" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                        </svg>
                    </div>
                    <p style="margin: 0 0 8px 0; font-size: 0.813rem; color: rgba(253, 126, 20, 0.9); font-weight: 500;">False Positives</p>
                    <p style="margin: 0; font-size: 1.75rem; font-weight: 700; color: #fd7e14;">${metrics.false_positives.toLocaleString()}</p>
                </div>

                <div style="background: linear-gradient(135deg, rgba(220, 53, 69, 0.1) 0%, rgba(220, 53, 69, 0.02) 100%); border: 1px solid rgba(220, 53, 69, 0.3); border-radius: 12px; padding: 20px; text-align: center; transition: all 0.3s ease;">
                    <div style="width: 48px; height: 48px; background: rgba(220, 53, 69, 0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#dc3545" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="15" y1="9" x2="9" y2="15"></line>
                            <line x1="9" y1="9" x2="15" y2="15"></line>
                        </svg>
                    </div>
                    <p style="margin: 0 0 8px 0; font-size: 0.813rem; color: rgba(220, 53, 69, 0.9); font-weight: 500;">False Negatives</p>
                    <p style="margin: 0; font-size: 1.75rem; font-weight: 700; color: #dc3545;">${metrics.false_negatives.toLocaleString()}</p>
                </div>
            </div>
        </div>
    ` : '<div style="text-align: center; padding: 60px 20px;"><div style="width: 64px; height: 64px; border: 3px solid rgba(0,0,0,0.1); border-top-color: #000; border-radius: 50%; margin: 0 auto 20px; animation: spin 1s linear infinite;"></div><p style="color: rgba(0,0,0,0.6); font-size: 1.125rem;">Loading model metrics...</p></div>';

    page.innerHTML = `
        <div style="padding: 32px; max-width: 1400px; margin: 0 auto;">
            <!-- Page Header -->
            <div style="margin-bottom: 40px;">
                <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 12px;">
                    <div style="width: 64px; height: 64px; background: linear-gradient(135deg, rgba(138, 43, 226, 0.2) 0%, rgba(75, 0, 130, 0.2) 100%); border: 2px solid rgba(138, 43, 226, 0.4); border-radius: 16px; display: flex; align-items: center; justify-content: center; box-shadow: 0 8px 24px rgba(138, 43, 226, 0.3);">
                        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 50 50">
                            <path fill="#8a2be2" d="M 23 1 C 15.773438 1 10.445313 3.492188 7 7.398438 C 3.554688 11.308594 2 16.558594 2 22 C 2 26.40625 3.363281 30.507813 5.675781 33.867188 C 7.769531 36.914063 9 40.519531 9 44.199219 L 9 49 L 11 49 L 11 44.199219 C 11 40.078125 9.628906 36.085938 7.324219 32.734375 C 5.234375 29.695313 4 25.992188 4 22 C 4 16.941406 5.445313 12.191406 8.5 8.726563 C 11.554688 5.257813 16.226563 3 23 3 C 29.800781 3 34.207031 4.980469 37.117188 8.007813 C 40.027344 11.03125 41.472656 15.203125 42.007813 19.71875 L 42.03125 19.921875 L 46.828125 28.1875 C 47.074219 28.632813 46.949219 29.078125 46.515625 29.324219 L 42 31.582031 L 42 37.597656 C 42 41.339844 38.921875 44.25 35.191406 43.90625 L 35.175781 43.902344 L 31 43.632813 L 31 49 L 33 49 L 33 45.765625 L 35.007813 45.894531 C 39.878906 46.351563 44 42.457031 44 37.597656 L 44 32.816406 L 47.484375 31.074219 C 48.847656 30.316406 49.324219 28.566406 48.574219 27.214844 L 48.570313 27.207031 L 43.921875 19.199219 C 43.328125 14.515625 41.804688 9.996094 38.558594 6.617188 C 35.242188 3.171875 30.199219 1 23 1 Z M 27 8 L 27 10.101563 C 26.363281 10.230469 25.773438 10.488281 25.25 10.835938 L 23.757813 9.34375 L 22.34375 10.757813 L 23.835938 12.25 C 23.488281 12.773438 23.230469 13.363281 23.101563 14 L 21 14 L 21 16 L 23.101563 16 C 23.230469 16.636719 23.488281 17.226563 23.835938 17.75 L 22.34375 19.242188 L 23.757813 20.65625 L 25.25 19.164063 C 25.773438 19.511719 26.363281 19.769531 27 19.898438 L 27 22 L 29 22 L 29 19.898438 C 29.636719 19.769531 30.226563 19.511719 30.75 19.164063 L 32.242188 20.65625 L 33.65625 19.242188 L 32.164063 17.75 C 32.511719 17.226563 32.769531 16.636719 32.898438 16 L 35 16 L 35 14 L 32.898438 14 C 32.769531 13.363281 32.511719 12.773438 32.164063 12.25 L 33.65625 10.757813 L 32.242188 9.34375 L 30.75 10.835938 C 30.226563 10.488281 29.636719 10.230469 29 10.101563 L 29 8 Z M 28 12 C 29.667969 12 31 13.332031 31 15 C 31 16.667969 29.667969 18 28 18 C 26.332031 18 25 16.667969 25 15 C 25 13.332031 26.332031 12 28 12 Z M 15 16 L 15 18.101563 C 14.363281 18.230469 13.78125 18.492188 13.253906 18.84375 L 11.757813 17.34375 L 10.34375 18.757813 L 11.84375 20.257813 C 11.496094 20.78125 11.238281 21.367188 11.109375 22 L 9 22 L 9 24 L 11.101563 24 C 11.230469 24.636719 11.488281 25.226563 11.835938 25.75 L 10.34375 27.242188 L 11.757813 28.65625 L 13.25 27.164063 C 13.773438 27.511719 14.363281 27.769531 15 27.898438 L 15 30 L 17 30 L 17 27.898438 C 17.636719 27.769531 18.226563 27.511719 18.75 27.164063 L 20.242188 28.65625 L 21.65625 27.242188 L 20.164063 25.75 C 20.511719 25.226563 20.769531 24.636719 20.898438 24 L 23 24 L 23 22 L 20.890625 22 C 20.761719 21.367188 20.503906 20.78125 20.15625 20.257813 L 21.65625 18.757813 L 20.242188 17.34375 L 18.746094 18.84375 C 18.21875 18.492188 17.636719 18.230469 17 18.101563 L 17 16 Z M 16 20 C 17.667969 20 19 21.332031 19 23 C 19 24.667969 17.667969 26 16 26 C 14.332031 26 13 24.667969 13 23 C 13 21.332031 14.332031 20 16 20 Z"></path>
                        </svg>
                    </div>
                    <div>
                        <h1 style="margin: 0 0 8px 0; font-size: 2.25rem; font-weight: 800; color: #000;">
                            RL Model Dashboard
                        </h1>
                        <p style="margin: 0; font-size: 1rem; color: rgba(0,0,0,0.6); font-weight: 400;">
                            Monitor reinforcement learning model performance and metrics in real-time
                        </p>
                    </div>
                </div>
            </div>

            <!-- Main Content Card -->
            <div style="background: #fff; border: 1px solid rgba(0,0,0,0.1); border-radius: 20px; padding: 40px; box-shadow: 0 4px 16px rgba(0,0,0,0.1);">
                ${metricsHtml}
            </div>
        </div>
    `;

    return page;
}
