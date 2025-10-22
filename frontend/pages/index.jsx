// import React, { useState } from "react";
// import axios from "axios";

// export default function App(){
//   const [file, setFile] = useState(null);
//   const [res, setRes] = useState(null);
//   const [loading, setLoading] = useState(false);

//   const upload = async () => {
//     if(!file) return alert("Choose PDF");
//     setLoading(true);
//     const fd = new FormData();
//     fd.append("file", file);
//     try{
//       const r = await axios.post("http://localhost:8080/parse/", fd, { headers: { "Content-Type": "multipart/form-data" } });
//       setRes(r.data);
//     }catch(e){
//       alert("Error: " + (e.response?.data || e.message));
//     }finally{
//       setLoading(false);
//     }
//   };

//   return (
//     <div className="container">
//       <div className="header">
//         <h1 className="h1">CardIQ — Credit Card Statement Parser</h1>
//         <div className="small">Unique hybrid parser • Local</div>
//       </div>

//       <div className="card">
//         <input className="input" type="file" accept="application/pdf" onChange={e=>setFile(e.target.files[0])} />
//         <div style={{marginTop:12}}>
//           <button className="btn" onClick={upload} disabled={loading}>{loading ? "Parsing..." : "Upload & Parse"}</button>
//         </div>
//       </div>

//       {res && (
//         <div className="card">
//           <h3>Detected Bank: <span className="small">{res.bank}</span></h3>
//           <div style={{marginTop:8}}>
//             {Object.entries(res.fields).map(([k,v]) => (
//               <div key={k} className="field">
//                 <div>
//                   <div style={{fontWeight:600}}>{k}</div>
//                   <div className="small">{v.snippet || ""}</div>
//                 </div>
//                 <div style={{textAlign:"right"}}>
//                   <div>{v.value ?? "—"}</div>
//                   <div className="small">conf: {(v.confidence*100).toFixed(1)}%</div>
//                 </div>
//               </div>
//             ))}
//           </div>
//         </div>
//       )}

//       <div style={{marginTop:16}} className="small">Tip: Try different bank statements. Confidence is semantic score + heuristic score.</div>
//     </div>
//   );
// }


import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);



