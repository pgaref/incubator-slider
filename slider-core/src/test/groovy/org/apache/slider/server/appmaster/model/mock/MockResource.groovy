/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.apache.slider.server.appmaster.model.mock

import org.apache.hadoop.yarn.api.records.Resource
import org.apache.hadoop.yarn.api.records.ValueRanges

class MockResource extends Resource {
  int memory
  int virtualCores

  MockResource(int memory = 0, int vcores = 0) {
    this.memory = memory
    this.virtualCores = vcores
  }
  
  @Override
  public int compareTo(Resource other) {
    int diff = this.getMemory() - other.getMemory();
    if (diff == 0) {
      diff = this.getVirtualCores() - other.getVirtualCores();
    }
    return diff;
  }

  public void setMemorySize(long memory) {
    this.memory = memory
  }

  public long getMemorySize() {
    return memory
  }

  @Override
  ValueRanges getPorts() {
    return null
  }

  @Override
  void setPorts(ValueRanges ports) {

  }
}
