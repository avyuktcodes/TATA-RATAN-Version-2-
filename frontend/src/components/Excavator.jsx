import React from 'react';
import './Excavator.css';

const Excavator = () => {
  return (
    <div className="excavator-container">
      <div className="coal-pile">⬛⬛⬛</div>
      <div className="excavator-vehicle">🚜</div>
      <div className="thinking-text">Digging through the Neo4j Graph...</div>
    </div>
  );
};

export default Excavator;
