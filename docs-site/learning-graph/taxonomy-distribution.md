# Taxonomy Distribution Report

## Overview

- **Total Concepts**: 124
- **Number of Taxonomies**: 11
- **Average Concepts per Taxonomy**: 11.3

## Distribution Summary

| Category | TaxonomyID | Count | Percentage | Status |
|----------|-----------|-------|------------|--------|
| Connections and HTTP Engine | CONN | 17 | 13.7% | ✅ |
| Facade Operations | FAC | 16 | 12.9% | ✅ |
| Storage Profiles and Settings | PROF | 14 | 11.3% | ✅ |
| Protocols and Registry | PROTO | 14 | 11.3% | ✅ |
| Ecosystem and Foundations | ECO | 12 | 9.7% | ✅ |
| Paths, Schemes and Location Policy | PATH | 11 | 8.9% | ✅ |
| Read Access and Streams | READ | 11 | 8.9% | ✅ |
| Stream Transforms | XFRM | 9 | 7.3% | ✅ |
| Backends | BACK | 8 | 6.5% | ✅ |
| Errors, Testing and Maintenance | MAINT | 7 | 5.6% | ✅ |
| Package Surface and Install | SURF | 5 | 4.0% | ✅ |

## Visual Distribution

```
Connections and HTTP Engi ██████  17 ( 13.7%)
Facade Operations         ██████  16 ( 12.9%)
Storage Profiles and Sett █████  14 ( 11.3%)
Protocols and Registry    █████  14 ( 11.3%)
Ecosystem and Foundations ████  12 (  9.7%)
Paths, Schemes and Locati ████  11 (  8.9%)
Read Access and Streams   ████  11 (  8.9%)
Stream Transforms         ███   9 (  7.3%)
Backends                  ███   8 (  6.5%)
Errors, Testing and Maint ██   7 (  5.6%)
Package Surface and Insta ██   5 (  4.0%)
```

## Balance Analysis

### ✅ No Over-Represented Categories

All categories are under the 30% threshold. Good balance!

## Category Details

### Connections and HTTP Engine (CONN)

**Count**: 17 concepts (13.7%)

**Concepts**:

- 179. ConnectionProtocol
- 180. create_connection
- 181. Target Families
- 182. Leaf Connections
- 183. Decorator Connections
- 184. HTTPConnection
- 185. S3Connection
- 186. SSHConnection
- 187. SFTPConnection
- 188. NullConnection
- 189. Bastion Tunnels
- 190. Connection Errors
- 191. HTTP Request Engine
- 192. HTTP Retry Policy
- 193. HTTP Response Handling
- *...and 2 more*

### Facade Operations (FAC)

**Count**: 16 concepts (12.9%)

**Concepts**:

- 143. StorageFacade
- 144. from_path
- 145. for_local
- 146. Facade Lifecycle
- 147. Capability Checks
- 148. Read and Write
- 149. Streaming Reads and Writes
- 150. Enumerate and List
- 151. StorageEntry
- 152. Metadata Queries
- 153. Delete
- 154. Directory Operations
- 155. Parent Creation
- 156. Copy Within a Backend
- 157. copy_between
- *...and 1 more*

### Storage Profiles and Settings (PROF)

**Count**: 14 concepts (11.3%)

**Concepts**:

- 129. Storage Profiles
- 130. Auth Profiles
- 131. Provider Types
- 132. StorageProfileSpec
- 133. Implemented Flag
- 134. Settings-Only Providers
- 135. STORAGE_REGISTRY
- 136. S3 Flavours
- 137. SFTP Profile
- 138. HTTP Profile
- 139. Local Profile
- 140. Profile Emission
- 141. Named Profiles
- 142. resolve_storage

### Protocols and Registry (PROTO)

**Count**: 14 concepts (11.3%)

**Concepts**:

- 196. Storage Protocols
- 197. Runtime-Checkable Protocols
- 198. Read Protocol
- 199. Write Protocol
- 200. Enumerate Protocol
- 201. Delete Protocol
- 202. Metadata Protocol
- 203. Copy Protocol
- 204. Directory Protocol
- 205. Ranged Read Protocol
- 206. Backend Registry
- 207. register_storage_backend
- 208. Backend Lookup
- 209. Facade Dispatch

### Ecosystem and Foundations (ECO)

**Count**: 12 concepts (9.7%)

**Concepts**:

- 101. Byte Storage Endpoints
- 102. URL Schemes and Paths
- 103. Object Storage Model
- 104. Binary Streams
- 105. Transport Responsibility Boundary
- 106. Mountainash Ecosystem
- 107. mountainash-auth-client
- 108. mountainash-settings
- 109. mountainash-files
- 110. mountainash Relations Readers
- 111. Credential Delegation
- 112. Format-Agnostic Storage

### Paths, Schemes and Location Policy (PATH)

**Count**: 11 concepts (8.9%)

**Concepts**:

- 118. SchemeSpec Registry
- 119. Scheme Dispatch
- 120. StoragePath
- 121. S3 Bucket and Key Parsing
- 122. Suffix Chains
- 123. LocationPolicy
- 124. Local Root Confinement
- 125. Remote Allow-List
- 126. Profile-Granted Hosts
- 127. LocationNotAllowed
- 128. Credential Redaction

### Read Access and Streams (READ)

**Count**: 11 concepts (8.9%)

**Concepts**:

- 159. Read Access Modes
- 160. Sequential Access
- 161. Random Access
- 162. Buffered Access
- 163. RangePolicy
- 164. RangedReader
- 165. Sequential Stream Adapters
- 166. Deferred Read Errors
- 167. Stream Ownership
- 168. materialize
- 169. Native Local Handles

### Stream Transforms (XFRM)

**Count**: 9 concepts (7.3%)

**Concepts**:

- 170. Stream Transform
- 171. Transform Pipeline
- 172. Transform Direction
- 173. Gzip Transform
- 174. GPG Transform
- 175. Suffix Inference
- 176. Transforms and Random Access
- 177. Streaming Gzip Encoder
- 178. Transform Layer Ownership

### Backends (BACK)

**Count**: 8 concepts (6.5%)

**Concepts**:

- 210. Mixin Composition
- 211. Support Matrix
- 212. Local Backend
- 213. S3 Backend
- 214. S3 Family Registration
- 215. SFTP Backend
- 216. HTTP Backend
- 217. Backend Divergences

### Errors, Testing and Maintenance (MAINT)

**Count**: 7 concepts (5.6%)

**Concepts**:

- 218. TransportError Hierarchy
- 219. Backend Error Mapping
- 220. BackendNotImplementedError
- 221. Conformance Tests
- 222. Registry Completeness Tests
- 223. Slim Install Test
- 224. Adding a Backend

### Package Surface and Install (SURF)

**Count**: 5 concepts (4.0%)

**Concepts**:

- 113. Base Install
- 114. Optional Extras
- 115. MissingExtraError
- 116. Lazy Package Root
- 117. storage() Factory

## Recommendations

- ✅ **Excellent balance**: Categories are evenly distributed (spread: 9.7%)
- ✅ **MISC category minimal**: Good categorization specificity

### Educational Use Recommendations

- Use taxonomy categories for color-coding in graph visualizations
- Design curriculum modules based on taxonomy groupings
- Create filtered views for focused learning paths
- Use categories for assessment organization
- Enable navigation by topic area in interactive tools

---

*Report generated by ibook graph taxonomy-report*
